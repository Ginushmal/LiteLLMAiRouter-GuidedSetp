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
from pathlib import Path

from model_pipeline.config import Config, load_config
from model_pipeline.http import HttpClient, ScrapeRecorder


def _latest_html(cfg: Config, provider: str) -> str:
    provider_dir = cfg.raw_dir / provider
    if not provider_dir.exists():
        return ""
    htmls = sorted(provider_dir.glob("*.html"), key=lambda p: p.stat().st_mtime)
    return htmls[-1].read_text(encoding="utf-8", errors="replace") if htmls else ""


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
    from model_pipeline.providers.registry import build_adapters
    from model_pipeline.scoring.aa import AaClient

    cfg = load_config(args.config)
    http = HttpClient()
    recorder = ScrapeRecorder(cfg.raw_dir, cfg.logs_dir)

    adapters = build_adapters(cfg, http, recorder)
    models = []
    for adapter in adapters:
        fetched = adapter.fetch_all()
        print(f"  {adapter.name}: {len(fetched)} servable models")
        models.extend(fetched)

    print("  fetching Artificial Analysis canonical models...")
    canonical = AaClient(cfg, http, recorder).canonical_models()
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


# --------------------------------------------------------------------------- #
# score
# --------------------------------------------------------------------------- #
def cmd_score(args: argparse.Namespace) -> int:
    from model_pipeline.dedup.mappings_csv import read_mappings
    from model_pipeline.emit.output import build_payload, write_json, write_markdown
    from model_pipeline.emit.report import write_report
    from model_pipeline.emit.snapshot import read_snapshot
    from model_pipeline.providers.registry import build_adapters
    from model_pipeline.scoring.aa import AaClient
    from model_pipeline.scoring.pipeline import score

    cfg = load_config(args.config)
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
    canonical = AaClient(cfg, http, recorder).canonical_models()
    adapters = {a.name: a for a in build_adapters(cfg, http, recorder)}
    models_index = {(m.provider, m.model_id): m for m in models}
    http.close()

    result = score(mappings, models_index, canonical, adapters, cfg)
    payload = build_payload(result, cfg)
    write_json(cfg.output_dir / "tier-output.json", payload)
    write_markdown(cfg.output_dir / "tier-output.md", payload)
    write_report(cfg.output_dir / "tier-ranking.md", result, cfg)

    print(f"score complete: SOTA intelligence = {result.sota_intelligence}")
    for tier in result.tiers:
        print(f"  {tier.name:11} -> {tier.model_group:16} {len(tier.deployments)} deployments (pool {tier.pool_size})")
    print(f"  cost methods: {result.cost_methods}")
    print("  wrote output/tier-output.json, output/tier-output.md, output/tier-ranking.md")
    print("\nReview output/tier-output.json, then run: populate")
    return 0


# --------------------------------------------------------------------------- #
# populate
# --------------------------------------------------------------------------- #
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
    report = sync(payload, cfg, http, apply=not args.dry_run)
    http.close()

    verb = "would apply" if args.dry_run else "applied"
    print(f"populate {verb}: {report.summary()}")
    for key in report.added:
        print(f"  + {key}")
    for key in report.updated:
        print(f"  ~ {key}")
    for key in report.deleted:
        print(f"  - {key}")
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

    sub.add_parser("fetch", help="fetch providers + dedup -> mappings.csv")
    sub.add_parser("score", help="mappings + AA + config -> tier-output.json")
    populate = sub.add_parser("populate", help="tier-output.json -> LiteLLM")
    populate.add_argument("--dry-run", action="store_true", help="show the diff without applying")
    run = sub.add_parser("run", help="fetch -> score -> populate in one go (no review gates)")
    run.add_argument("--dry-run", action="store_true", help="score for real, but preview the populate diff")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        return cmd_fetch(args)
    if args.command == "score":
        return cmd_score(args)
    if args.command == "populate":
        return cmd_populate(args)
    if args.command == "run":
        return cmd_run(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
