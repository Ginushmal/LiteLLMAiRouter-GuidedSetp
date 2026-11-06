"""model-pipeline CLI.

Three independent phases with file-based handoffs:

    fetch     providers -> dedup        -> output/mappings.csv (+ snapshot)
    score     mappings + AA + config    -> output/tier-output.json/.md
    populate  tier-output.json          -> LiteLLM management API

Each phase can be re-run on its own. `fetch` and `score` halt for human review.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from urllib.parse import urlparse

from model_pipeline.config import Config, load_config, parse_as_of
from model_pipeline.http import HttpClient, ScrapeRecorder

_AS_OF_HELP = (
    "evaluate time-of-day prices at this ISO 8601 timestamp (must carry a "
    "timezone, e.g. 2026-10-22T18:00Z); overrides pricing.as_of for this run"
)
_NO_CACHE_HELP = (
    "bypass on-disk snapshot cache (output/aa_snapshot.json) and force a "
    "fresh fetch from the Artificial Analysis API"
)


def _latest_html(cfg: Config, provider: str) -> str:
    provider_dir = cfg.raw_dir / provider
    if not provider_dir.exists():
        return ""
    htmls = sorted(provider_dir.glob("*.html"), key=lambda p: p.stat().st_mtime)
    return htmls[-1].read_text(encoding="utf-8", errors="replace") if htmls else ""


def _as_of_for_run(cfg: Config, args: argparse.Namespace):
    """The run's schedule evaluation instant: ``--as-of`` wins over config.

    ``populate`` takes no flag, so ``getattr`` keeps the helper usable there.
    """
    override = getattr(args, "as_of", None)
    return parse_as_of(override) if override else cfg.pricing.as_of


def _print_limit_warnings(flagged: dict[str, list[str]]) -> None:
    """Print the token-limit problems a reviewer must see (never silently guess)."""
    from model_pipeline.limits import (
        FLAG_OUTPUT_EQUALS_CONTEXT,
        FLAG_OUTPUT_NOT_BELOW_CONTEXT,
        FLAG_UNRESOLVED,
    )

    notes = (
        (FLAG_UNRESOLVED, "have no output limit (no catalog entry publishes one)"),
        (FLAG_OUTPUT_EQUALS_CONTEXT, "are flagged output==context (catalog value looks copied)"),
        (FLAG_OUTPUT_NOT_BELOW_CONTEXT, "are flagged output>=context (impossible)"),
    )
    for flag, note in notes:
        items = sorted(key for key, flags in flagged.items() if flag in flags)
        if not items:
            continue
        print(f"  warning: {len(items)} model(s) {note}:")
        for item in items[:10]:
            print(f"    {item}")
        if len(items) > 10:
            print(f"    … and {len(items) - 10} more (see the ranking report)")


def _print_plan_warnings(adapter) -> None:
    """Report models dropped because the subscription plan does not serve them.

    Adapters that gate on a plan expose ``plan``, ``plan_excluded`` and
    ``plan_unverified``; other adapters expose none of it and print nothing.
    """
    plan = getattr(adapter, "plan", "")
    excluded = getattr(adapter, "plan_excluded", [])
    unverified = getattr(adapter, "plan_unverified", [])
    if excluded:
        print(
            f"  warning: {len(excluded)} model(s) need a higher {adapter.name} "
            f"plan than {plan}:"
        )
        for model_id, required in excluded[:10]:
            print(f"    {model_id} (needs {required})")
        if len(excluded) > 10:
            print(f"    … and {len(excluded) - 10} more")
    if unverified:
        print(
            f"  warning: {len(unverified)} {adapter.name} model(s) have no plan data "
            "and were dropped (never assumed available):"
        )
        for model_id in unverified[:10]:
            print(f"    {model_id}")
        if len(unverified) > 10:
            print(f"    … and {len(unverified) - 10} more")


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #
def cmd_fetch(args: argparse.Namespace) -> int:
    from model_pipeline.dedup.jev import JevClient
    from model_pipeline.dedup.mapper import map_models
    from model_pipeline.dedup.mappings_csv import (
        low_confidence_rows,
        write_mappings,
    )
    from model_pipeline.emit.snapshot import write_snapshot
    from model_pipeline.emit.suggested_config import build_suggested, dump_suggested
    from model_pipeline.limits import apply_limits, fetch_catalog, models_dev_ids
    from model_pipeline.providers.registry import build_adapters
    from model_pipeline.scoring.aa import AaClient

    cfg = load_config(args.config)
    cfg.pricing.as_of = _as_of_for_run(cfg, args)
    http = HttpClient()
    recorder = ScrapeRecorder(cfg.raw_dir, cfg.logs_dir)

    adapters = build_adapters(cfg, http, recorder)
    models = []
    for adapter in adapters:
        fetched = adapter.fetch_all()
        print(f"  {adapter.name}: {len(fetched)} servable models")
        _print_plan_warnings(adapter)
        models.extend(fetched)

    print("  fetching token limits from models.dev...")
    resolver = fetch_catalog(cfg, http, recorder)
    if resolver is None:
        print("  warning: models.dev unreachable; token limits will be unresolved")
    else:
        print(f"  models.dev: {resolver.model_count} models")
    _print_limit_warnings(apply_limits(models, resolver, models_dev_ids(cfg)))

    no_cache = bool(getattr(args, "no_cache", False) or getattr(args, "refresh_aa", False))
    print("  fetching Artificial Analysis canonical models...")
    canonical = AaClient(cfg, http, recorder).canonical_models(use_cache=not no_cache)
    print(f"  canonical models: {len(canonical)}")

    print("  de-duplicating (exact match, then Jev for the rest)...")
    mappings = map_models(models, canonical, cfg, JevClient(cfg, http))

    write_mappings(cfg.output_dir / "mappings.csv", mappings)
    write_snapshot(cfg.output_dir / "models_snapshot.json", models)

    htmls = [_latest_html(cfg, a.name) for a in adapters if _latest_html(cfg, a.name)]
    suggested = build_suggested(htmls, cfg.task_profile.cache_hit_rate, cfg.task_profile.input_output_ratio)
    dump_suggested(cfg.output_dir / "suggested_config.yaml", suggested)

    http.close()

    low = low_confidence_rows(mappings)
    mapped = sum(1 for m in mappings if m.effective_slug)
    print(f"\nfetch complete: {len(mappings)} rows, {mapped} mapped.")
    print("  wrote output/mappings.csv, output/models_snapshot.json, output/suggested_config.yaml")
    if low:
        print(f"\nHALT: {len(low)} low-confidence row(s) need review:")
        for m in low[:15]:
            print(f"  {m.provider:12} {m.model_id:34} -> {m.canonical_slug} ({m.confidence:.2f})")
        print("\nEdit the 'override' column in output/mappings.csv, then run: score")
    else:
        print("No low-confidence rows. Review output/mappings.csv and run: score")
    return 0


def _print_pin_warnings(warnings: list[str]) -> None:
    """Surface pin warnings on stderr; the report and JSON carry them too."""
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)


def _tier_summary(tier) -> str:
    """One tier's deployment line, separating pinned from scored deployments."""
    pinned = sum(1 for d in tier.deployments if d.is_pinned)
    scored = len(tier.deployments) - pinned
    return (
        f"{tier.name:11} -> {tier.model_group:16} "
        f"{len(tier.deployments)} deployments ({pinned} pinned, {scored} scored, "
        f"pool {tier.pool_size})"
    )


# --------------------------------------------------------------------------- #
# score
# --------------------------------------------------------------------------- #
def cmd_score(args: argparse.Namespace) -> int:
    from model_pipeline.dedup.mappings_csv import low_confidence_rows, read_mappings
    from model_pipeline.emit.html_report import write_html
    from model_pipeline.emit.output import build_payload, write_json, write_markdown
    from model_pipeline.emit.report import write_report
    from model_pipeline.emit.snapshot import read_snapshot
    from model_pipeline.limits import apply_limits, fetch_catalog, models_dev_ids
    from model_pipeline.providers.registry import build_adapters
    from model_pipeline.scoring.aa import AaClient
    from model_pipeline.scoring.pipeline import score

    cfg = load_config(args.config)
    cfg.pricing.as_of = _as_of_for_run(cfg, args)
    http = HttpClient()
    recorder = ScrapeRecorder(cfg.raw_dir, cfg.logs_dir)

    mappings_path = cfg.output_dir / "mappings.csv"
    snapshot_path = cfg.output_dir / "models_snapshot.json"
    for path in (mappings_path, snapshot_path):
        if not path.exists():
            print(f"error: {path} not found. Run: fetch", file=sys.stderr)
            return 2

    mappings = read_mappings(mappings_path)
    models = read_snapshot(snapshot_path)

    # A snapshot written before token-limit resolution carries none. Resolve
    # them here so `score` still emits truthful limits; a re-run of `fetch`
    # persists them in the snapshot itself.
    if all(not m.limits_source for m in models):
        print("  no token limits in the snapshot; resolving from models.dev...")
        resolver = fetch_catalog(cfg, http, recorder)
        if resolver is None:
            print("  warning: models.dev unreachable; token limits will be unresolved")
        _print_limit_warnings(apply_limits(models, resolver, models_dev_ids(cfg)))

    canonical = AaClient(cfg, http, recorder).canonical_models()
    adapters = {a.name: a for a in build_adapters(cfg, http, recorder)}
    models_index = {(m.provider, m.model_id): m for m in models}
    http.close()

    result = score(mappings, models_index, canonical, adapters, cfg)
    payload = build_payload(result, cfg)
    low = low_confidence_rows(mappings)
    write_json(cfg.output_dir / "tier-output.json", payload)
    write_markdown(cfg.output_dir / "tier-output.md", payload)
    write_report(cfg.output_dir / "tier-ranking.md", result, cfg, low)
    write_html(cfg.output_dir / "tier-report.html", result, low)

    print(f"score complete: SOTA intelligence = {result.sota_intelligence}")
    _print_pin_warnings(result.pin_warnings)
    for tier in result.tiers:
        print(f"  {_tier_summary(tier)}")
    print(f"  cost methods: {result.cost_methods}")
    print("  wrote output/tier-output.json, output/tier-output.md, output/tier-ranking.md, output/tier-report.html")
    print("\nReview output/tier-output.json, then run: populate")
    return 0


# --------------------------------------------------------------------------- #
# refresh (fetch + score, never populate)
# --------------------------------------------------------------------------- #
def cmd_refresh(args: argparse.Namespace) -> int:
    """Run fetch -> score in one go, never touching LiteLLM.

    The one-click path for "what are the best models today": it refreshes the
    provider data, re-scores, and writes the readable reports. ``populate``
    is deliberately out of scope — use it explicitly when LiteLLM should change.
    """
    for step, handler in (
        ("fetch", cmd_fetch),
        ("score", cmd_score),
    ):
        print(f"\n===== {step} =====")
        rc = handler(args)
        if rc != 0:
            print(f"refresh stopped: '{step}' exited with code {rc}", file=sys.stderr)
            return rc
    print("\nrefresh complete: fetch -> score (reports written, LiteLLM untouched)")
    return 0


# --------------------------------------------------------------------------- #
# populate
# --------------------------------------------------------------------------- #
def _target_host(url: str) -> str:
    return urlparse(url).netloc or url


def _print_target(cfg: Config) -> None:
    url = cfg.litellm.base_url
    print(f"LiteLLM target: {url} ({_target_host(url)})")
    print(f"  auth: Bearer from env {cfg.litellm.master_key_env}")


def _print_server_details(details: dict, models: list[dict]) -> None:
    """Show what the target is before anything is written.

    Only the env-var name is printed for auth — never the key value.
    """
    from model_pipeline.models import ID_PREFIX

    status = details.get("status") or "unknown"
    db = details.get("db") or "unknown"
    print(f"  health: {status} (db: {db})")
    print(f"  version: {details.get('version') or 'unknown'}")

    managed = [
        m
        for m in models
        if str((m.get("model_info") or {}).get("id", "")).startswith(ID_PREFIX)
    ]
    groups = Counter(
        (m.get("model_info") or {}).get("model_group")
        or m.get("model_name")
        or "unknown"
        for m in managed
    )
    group_text = ", ".join(f"{name}: {count}" for name, count in sorted(groups.items()))
    suffix = f" ({group_text})" if group_text else ""
    print(f"  models: {len(models)} total, {len(managed)} pipeline-managed{suffix}")


def _print_changes(added, updated, deleted) -> None:
    for key in added:
        print(f"  + {key}")
    for key in updated:
        print(f"  ~ {key}")
    for key in deleted:
        print(f"  - {key}")


def _print_plan(plan) -> None:
    print(f"  pending changes: {plan.summary()}")
    _print_changes(plan.report.added, plan.report.updated, plan.report.deleted)


def _ask_apply(target: str, ask=input) -> bool:
    """One confirmation, defaulting to No on anything but y/yes."""
    try:
        answer = ask(f"\nApply these changes to {target}? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _cmd_populate_interactive(
    cfg: Config,
    payload: dict,
    client,
    ask=input,
    isatty=None,
    dry_run: bool = False,
) -> int:
    from model_pipeline.populate.sync import apply_plan, build_plan

    _print_target(cfg)
    try:
        details = client.server_details()
    except Exception as exc:  # noqa: BLE001 - report the target and the reason
        print(
            f"error: cannot read LiteLLM server at {cfg.litellm.base_url}: {exc}",
            file=sys.stderr,
        )
        return 2

    try:
        models = client.list_models()
    except Exception as exc:  # noqa: BLE001 - the master key may be rejected
        print(
            f"error: cannot list LiteLLM models at {cfg.litellm.base_url}: {exc}",
            file=sys.stderr,
        )
        return 2

    _print_server_details(details, models)
    plan = build_plan(payload, models)
    _print_plan(plan)

    if dry_run:
        print("  dry-run: no changes applied.")
        return 0

    interactive = sys.stdin.isatty() if isatty is None else isatty
    if not interactive:
        print("  stdin is not a terminal; preview only, LiteLLM unchanged.")
        return 0

    if not _ask_apply(_target_host(cfg.litellm.base_url), ask=ask):
        print("populate declined: LiteLLM unchanged")
        return 0

    report = apply_plan(client, plan)
    print(f"populate applied: {report.summary()}")
    _print_changes(report.added, report.updated, report.deleted)
    for err in report.errors:
        print(f"  ! {err}", file=sys.stderr)
    return 1 if report.errors else 0


def cmd_populate(args: argparse.Namespace) -> int:
    import json

    from model_pipeline.populate.sync import sync

    cfg = load_config(args.config)
    output_path = cfg.output_dir / "tier-output.json"
    if not output_path.exists():
        print(f"error: {output_path} not found. Run: score", file=sys.stderr)
        return 2
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    http = HttpClient()
    try:
        if getattr(args, "interactive", False):
            from model_pipeline.populate.litellm_client import LiteLLMClient

            try:
                client = LiteLLMClient(cfg, http)
            except RuntimeError as exc:
                print(
                    f"error: cannot populate {cfg.litellm.base_url}: {exc}",
                    file=sys.stderr,
                )
                return 2
            return _cmd_populate_interactive(
                cfg,
                payload,
                client,
                dry_run=bool(getattr(args, "dry_run", False)),
            )

        report = sync(payload, cfg, http, apply=not args.dry_run)
    finally:
        http.close()

    verb = "would apply" if args.dry_run else "applied"
    print(f"populate {verb}: {report.summary()}")
    _print_changes(report.added, report.updated, report.deleted)
    for err in report.errors:
        print(f"  ! {err}", file=sys.stderr)
    return 1 if report.errors else 0


# --------------------------------------------------------------------------- #
# run (all three phases in one go)
# --------------------------------------------------------------------------- #
def cmd_run(args: argparse.Namespace) -> int:
    """Run fetch -> score -> populate in one go, stopping on the first failure.

    This skips the human-review gates between phases (use the individual
    commands when you want to inspect mappings.csv / tier-output.json).
    """
    for step, handler in (
        ("fetch", cmd_fetch),
        ("score", cmd_score),
        ("populate", cmd_populate),
    ):
        print(f"\n===== {step} =====")
        rc = handler(args)
        if rc != 0:
            print(f"run stopped: '{step}' exited with code {rc}", file=sys.stderr)
            return rc
    print("\nrun complete: fetch -> score -> populate")
    return 0


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="model-pipeline", description=__doc__)
    parser.add_argument("--config", default=None, help="path to config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch providers + dedup -> mappings.csv")
    fetch.add_argument("--as-of", dest="as_of", default=None, help=_AS_OF_HELP)
    score = sub.add_parser("score", help="mappings + AA + config -> tier-output.json")
    score.add_argument("--as-of", dest="as_of", default=None, help=_AS_OF_HELP)
    refresh = sub.add_parser(
        "refresh", help="fetch -> score in one go (never populate) -> tier-report.html"
    )
    refresh.add_argument("--as-of", dest="as_of", default=None, help=_AS_OF_HELP)
    populate = sub.add_parser("populate", help="tier-output.json -> LiteLLM")
    populate.add_argument("--dry-run", action="store_true", help="show the diff without applying")
    populate.add_argument(
        "--interactive",
        action="store_true",
        help="show the target and diff, then confirm once before applying",
    )
    run = sub.add_parser("run", help="fetch -> score -> populate in one go (no review gates)")
    run.add_argument("--dry-run", action="store_true", help="score for real, but preview the populate diff")
    run.add_argument("--as-of", dest="as_of", default=None, help=_AS_OF_HELP)

    for p in (fetch, refresh, run):
        p.add_argument(
            "--no-cache",
            action="store_true",
            default=False,
            help=_NO_CACHE_HELP,
        )
        p.add_argument(
            "--refresh-aa",
            action="store_true",
            default=False,
            help=_NO_CACHE_HELP,
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001, S110 - best-effort console encoding
        pass
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        return cmd_fetch(args)
    if args.command == "score":
        return cmd_score(args)
    if args.command == "refresh":
        return cmd_refresh(args)
    if args.command == "populate":
        return cmd_populate(args)
    if args.command == "run":
        return cmd_run(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
