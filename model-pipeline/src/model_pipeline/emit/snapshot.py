"""Persist fetched provider models (with pricing) between phases.

`fetch` writes this snapshot so `score` can run from files alone, without
re-fetching providers.
"""

from __future__ import annotations

import json
from pathlib import Path

from model_pipeline.models import RawModel, ResolvedPricing


def models_to_json(models: list[RawModel]) -> list[dict]:
    return [
        {
            "provider": m.provider,
            "model_id": m.model_id,
            "display_name": m.display_name,
            "endpoint_type": m.endpoint_type,
            "context_tokens": m.context_tokens,
            "supported_endpoints": m.supported_endpoints,
            "pricing": (m.pricing.as_dict() if m.pricing else None),
        }
        for m in models
    ]


def models_from_json(rows: list[dict]) -> list[RawModel]:
    models: list[RawModel] = []
    for r in rows:
        pricing = None
        if r.get("pricing"):
            p = r["pricing"]
            pricing = ResolvedPricing(
                input=p.get("input"),
                output=p.get("output"),
                cache_read=p.get("cache_read"),
                cache_write=p.get("cache_write"),
                provenance=p.get("provenance", {}),
                normalization=p.get("normalization", []),
            )
        models.append(
            RawModel(
                provider=r["provider"],
                model_id=r["model_id"],
                display_name=r["display_name"],
                endpoint_type=r.get("endpoint_type", "chat"),
                context_tokens=r.get("context_tokens"),
                supported_endpoints=r.get("supported_endpoints", []),
                pricing=pricing,
            )
        )
    return models


def write_snapshot(path: Path, models: list[RawModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(models_to_json(models), indent=1), encoding="utf-8")


def read_snapshot(path: Path) -> list[RawModel]:
    return models_from_json(json.loads(path.read_text(encoding="utf-8")))
