"""mappings.csv read/write.

The CSV is the human review gate between `fetch` and `score`. A reviewer can
fill the `override` column with a canonical slug to correct any row; `score`
honours the override over the computed mapping.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from model_pipeline.models import Mapping

FIELDS = [
    "provider",
    "model_id",
    "canonical_slug",
    "canonical_name",
    "variant",
    "method",
    "confidence",
    "low_confidence",
    "override",
    "probabilities",
]


def write_mappings(path: Path, mappings: list[Mapping]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for mp in mappings:
            writer.writerow(
                {
                    "provider": mp.provider,
                    "model_id": mp.model_id,
                    "canonical_slug": mp.canonical_slug or "",
                    "canonical_name": mp.canonical_name or "",
                    "variant": mp.variant,
                    "method": mp.method,
                    "confidence": f"{mp.confidence:.4f}",
                    "low_confidence": "yes" if mp.low_confidence else "",
                    "override": mp.override,
                    "probabilities": json.dumps(mp.probabilities, ensure_ascii=False),
                }
            )


def read_mappings(path: Path) -> list[Mapping]:
    mappings: list[Mapping] = []
    with path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            probabilities = {}
            raw_probs = row.get("probabilities", "")
            if raw_probs:
                try:
                    probabilities = json.loads(raw_probs)
                except Exception:
                    probabilities = {}
            mappings.append(
                Mapping(
                    provider=row["provider"],
                    model_id=row["model_id"],
                    canonical_slug=row.get("canonical_slug") or None,
                    canonical_name=row.get("canonical_name") or None,
                    variant=row.get("variant", ""),
                    method=row.get("method", "unmapped"),
                    confidence=float(row.get("confidence") or 0.0),
                    probabilities=probabilities,
                    override=(row.get("override") or "").strip(),
                    low_confidence=row.get("low_confidence", "") == "yes",
                )
            )
    return mappings


def low_confidence_rows(mappings: list[Mapping]) -> list[Mapping]:
    """Rows a reviewer should check: low confidence and not yet overridden."""
    return [m for m in mappings if m.low_confidence and not m.override]
