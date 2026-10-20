"""Artificial Analysis client.

Free-tier models list (`/api/v2/language/models/free`) provides the canonical
model identities plus the intelligence index, input/output/cache prices, and
`cost_per_task.total_cost` we use for scoring.

The snapshot is cached to disk so re-runs stay well under the free tier's
100 requests/day limit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model_pipeline.config import Config
from model_pipeline.http import HttpClient, ScrapeRecorder, ScrapeRecord
from model_pipeline.models import CanonicalModel


class AaClient:
    def __init__(self, cfg: Config, http: HttpClient, recorder: ScrapeRecorder):
        self.cfg = cfg
        self.http = http
        self.recorder = recorder
        self.cache_path: Path = cfg.output_dir / "aa_snapshot.json"

    def _record(self, url: str, resp=None, error: str = "", count: int | None = None) -> None:
        self.recorder.record(
            ScrapeRecord(
                provider="artificialanalysis",
                url=url,
                method="GET",
                status=(resp.status_code if resp is not None else None),
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                content_type=(resp.headers.get("content-type", "") if resp is not None else ""),
                parsed_count=count,
                error=error,
            ),
            body=(resp.text if resp is not None else ""),
        )

    def fetch_raw(self, use_cache: bool = True) -> list[dict[str, Any]]:
        if use_cache and self.cache_path.exists():
            return json.loads(self.cache_path.read_text(encoding="utf-8"))

        headers = {"x-api-key": self.cfg.secret(self.cfg.aa.api_key_env)}
        page = 1
        rows: list[dict[str, Any]] = []
        while True:
            url = f"{self.cfg.aa.free_url}?page={page}&page_size={self.cfg.aa.page_size}"
            try:
                resp = self.http.get(url, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                self._record(url, error=str(exc))
                raise
            batch = payload.get("data", [])
            self._record(url, resp=resp, count=len(batch))
            rows.extend(batch)
            if not (payload.get("pagination") or {}).get("has_more"):
                break
            page += 1

        self.cache_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        return rows

    def canonical_models(self, use_cache: bool = True) -> list[CanonicalModel]:
        return [to_canonical(r) for r in self.fetch_raw(use_cache=use_cache)]


def to_canonical(raw: dict[str, Any]) -> CanonicalModel:
    evaluations = raw.get("evaluations") or {}
    pricing = raw.get("pricing") or {}
    performance = raw.get("performance") or {}
    cost = raw.get("artificial_analysis_intelligence_index_cost") or {}
    cost_per_task = cost.get("cost_per_task") or {}
    creator = raw.get("model_creator") or {}
    # End-to-end response time is the latency the NMB penalty charges for. AA
    # publishes it only for models it has benchmarked; absence stays None.
    latency = performance.get("median_end_to_end_response_time_seconds")
    return CanonicalModel(
        slug=raw.get("slug", ""),
        name=raw.get("name", ""),
        creator=creator.get("name", ""),
        intelligence=evaluations.get("artificial_analysis_intelligence_index"),
        latency_seconds=float(latency) if isinstance(latency, (int, float)) else None,
        coding_index=evaluations.get("artificial_analysis_coding_index"),
        aa_input=pricing.get("price_1m_input_tokens"),
        aa_output=pricing.get("price_1m_output_tokens"),
        aa_cache_read=pricing.get("price_1m_cache_hit_tokens"),
        aa_cache_write=pricing.get("price_1m_cache_write_tokens"),
        aa_cost_per_task=cost_per_task.get("total_cost"),
        aa_token_counts=None,  # Pro-tier only; the free snapshot has no token counts
        aa_cost_breakdown=cost or None,
    )
