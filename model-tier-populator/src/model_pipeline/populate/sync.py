"""Diff-based, idempotent population of LiteLLM.

Reads ``tier-output.json``, compares the desired deployments against the current
LiteLLM model list (matched by ``model_info.id``), and applies only the needed
creates/updates/deletes. Re-running with the same input applies zero changes.

The diff covers both ``litellm_params`` and the ``model_info`` fields the
pipeline owns (base model, model group, token limits): a row whose stored limits
differ must still converge. Updates therefore use ``PATCH /model/{id}/update``,
which merges ``model_info`` per key — the legacy ``POST /model/update`` writes
``litellm_params`` but ignores ``model_info`` entirely. Because the PATCH merges,
fields the pipeline does not own (``member_auto_router``, ``db_model``, ...) are
never cleared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from model_pipeline.config import Config
from model_pipeline.http import HttpClient
from model_pipeline.models import ID_PREFIX, deployment_id
from model_pipeline.populate.litellm_client import LiteLLMClient

# Fields we set and therefore compare for change detection.
# ``api_key`` is deliberately excluded: /model/info masks it, so comparing it
# would report a change on every run.
_COMPARED_PARAM_KEYS = (
    "model",
    "api_base",
    "order",
    "input_cost_per_token",
    "output_cost_per_token",
    "cache_read_input_token_cost",
    "cache_creation_input_token_cost",
)

# Pipeline-owned ``model_info`` fields: compared for drift and written back.
# Server-managed keys never appear here, so they cannot cause false diffs.
_COMPARED_INFO_KEYS = (
    "base_model",
    "model_group",
    "max_input_tokens",
    "max_output_tokens",
    "max_tokens",
)

# Everything the pipeline may put in a PATCH body's model_info (identity included).
_WRITABLE_INFO_KEYS = ("id", *_COMPARED_INFO_KEYS)


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"added={len(self.added)} updated={len(self.updated)} "
            f"deleted={len(self.deleted)} unchanged={self.unchanged} "
            f"errors={len(self.errors)}"
        )


@dataclass
class SyncPlan:
    """A computed diff, before any write.

    ``desired`` and ``current`` are needed to apply the plan; ``report`` carries
    the observable added/updated/deleted/unchanged sets so a preview and the
    subsequent apply can never disagree.
    """

    desired: dict[str, dict] = field(default_factory=dict)
    current: dict[str, dict] = field(default_factory=dict)
    report: SyncReport = field(default_factory=SyncReport)

    def summary(self) -> str:
        report = self.report
        return (
            f"added={len(report.added)} updated={len(report.updated)} "
            f"deleted={len(report.deleted)} unchanged={report.unchanged}"
        )


def _close(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= max(1e-12, abs(float(a)) * 1e-6)
    return a == b


def _params_differ(desired: dict, current: dict) -> bool:
    for key in _COMPARED_PARAM_KEYS:
        if key in desired and not _close(desired.get(key), current.get(key)):
            return True
    return bool(
        "extra_headers" in desired
        and desired.get("extra_headers") != current.get("extra_headers")
    )


def _info_differ(desired: dict, current: dict) -> bool:
    """Only a field we actually set can drift; an unset desired value is ignored."""
    for key in _COMPARED_INFO_KEYS:
        value = desired.get(key)
        if value is not None and not _close(value, current.get(key)):
            return True
    return False


def _update_body(desired: dict) -> dict:
    """PATCH body for one deployment: its params plus pipeline-owned model_info.

    Sending only owned ``model_info`` keys is what preserves the keys the
    pipeline does not own — the endpoint merges per key.
    """
    info = desired.get("model_info") or {}
    return {
        "model_name": desired.get("model_name"),
        "litellm_params": desired.get("litellm_params", {}),
        "model_info": {
            key: value
            for key, value in info.items()
            if key in _WRITABLE_INFO_KEYS and value is not None
        },
    }


def _current_index(models: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for m in models:
        info = m.get("model_info") or {}
        mid = info.get("id") or m.get("model_id")
        if isinstance(mid, str) and mid.startswith(ID_PREFIX):
            index[mid] = m
    return index


def build_plan(payload: dict, current_models: list[dict]) -> SyncPlan:
    """Compute the diff without writing anything.

    ``current_models`` is the ``data`` list from ``GET /model/info``. Splitting
    this from the apply step lets interactive mode show exactly the plan it will
    later apply.
    """
    desired: dict[str, dict] = {}
    for tier in payload.get("tiers", []):
        for dep in tier.get("deployments", []):
            # ``litellm_params`` on a deployment record is the full /model/new
            # payload (model_name + litellm_params + model_info).
            full_payload = dep["litellm_params"]
            info = full_payload.setdefault("model_info", {})
            mid = info.get("id") or deployment_id(
                dep["model_group"], dep["provider"], dep["model_id"]
            )
            info["id"] = mid
            full_payload.setdefault("model_id", mid)
            desired[mid] = full_payload

    current = _current_index(current_models)

    to_add = [k for k in desired if k not in current]
    to_update = [
        k
        for k in desired
        if k in current
        and (
            _params_differ(desired[k]["litellm_params"], current[k].get("litellm_params", {}))
            or _info_differ(desired[k].get("model_info", {}), current[k].get("model_info", {}))
        )
    ]
    to_delete = [k for k in current if k not in desired]
    report = SyncReport(
        added=to_add,
        updated=to_update,
        deleted=to_delete,
        unchanged=len(desired) - len(to_add) - len(to_update),
    )
    return SyncPlan(desired=desired, current=current, report=report)


def apply_plan(client: LiteLLMClient, plan: SyncPlan) -> SyncReport:
    """Apply a previously computed plan, returning the write report."""
    report = SyncReport(
        added=list(plan.report.added),
        updated=list(plan.report.updated),
        deleted=list(plan.report.deleted),
        unchanged=plan.report.unchanged,
    )
    for key in plan.report.added:
        _apply(client.add_model(plan.desired[key]), key, report)
    for key in plan.report.updated:
        _apply(
            client.patch_model(key, _update_body(plan.desired[key])), key, report
        )
    for key in plan.report.deleted:
        _apply(client.delete_model(key), key, report)
    return report


def sync(payload: dict, cfg: Config, http: HttpClient, apply: bool = True) -> SyncReport:
    client = LiteLLMClient(cfg, http)
    plan = build_plan(payload, client.list_models())
    if not apply:
        return SyncReport(
            added=list(plan.report.added),
            updated=list(plan.report.updated),
            deleted=list(plan.report.deleted),
            unchanged=plan.report.unchanged,
        )
    return apply_plan(client, plan)


def _apply(resp, key: str, report: SyncReport) -> None:
    if resp.status_code >= 300:
        report.errors.append(f"{key}: HTTP {resp.status_code} {resp.text[:160]}")
