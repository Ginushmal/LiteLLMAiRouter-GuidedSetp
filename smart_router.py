#!/usr/bin/env python3
"""
Dynamic LLM router — sample implementation.

Builds a tiered model-recommendation list (Ultra / Pro / Flash / Flash Lite) using
three economic ideas:

  1. Pareto frontier   — drop any model that is both more expensive and dumber than
                         another model (mathematically obsolete).
  2. SOTA-relative tiers — tier floors are fractions of the current best intelligence,
                         so tiers re-scale automatically as new models ship.
  3. NMB selection     — within a tier, rank by Net Monetary Benefit
                         NMB = (lambda * intelligence) - cost - (mu * latency),
                         selecting the best, removing it, and repeating to get the
                         top-K candidates per tier.

Data sources (no vendor SDK required, stdlib only):
  * live model list : GET https://api.commandcode.ai/provider/v1/models  (needs API key)
  * costs + context : https://commandcode.ai/models  (HTML table: intelligence, prices)
  * cost metadata   : https://cdn.jsdelivr.net/npm/command-code@latest/.../models.md

Outputs (written next to this script):
  smart_router_output.json  — machine-readable top models per tier with full stats
  smart_router_output.md    — human-readable report
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #

API_BASE = "https://api.commandcode.ai/provider/v1"
MODELS_PAGE_URL = "https://commandcode.ai/models"
MODEL_PAGE_BASE = "https://commandcode.ai/models/"
MODELS_MD_URL = (
    "https://cdn.jsdelivr.net/npm/command-code@latest/"
    "dist/bundled/command-code-knowledge/reference/models.md"
)

# Tier floors are fractions of the SOTA intelligence score (the best score still on
# the Pareto frontier). A model joins the highest tier whose floor it meets, so a
# model is Ultra when I >= 0.90*I_max, Pro when 0.80*I_max <= I < 0.90*I_max, etc.
# `lam` is willingness-to-pay in dollars per point of intelligence for that tier.
TIERS = [
    {"name": "Ultra", "floor_frac": 0.90, "lam": 15.0},
    {"name": "Pro", "floor_frac": 0.80, "lam": 1.0},
    {"name": "Flash", "floor_frac": 0.50, "lam": 0.2},
    {"name": "Flash Lite", "floor_frac": 0.00, "lam": 0.05},
]

TOP_N = 5  # candidates per tier

# Which single dollar figure is "Cost" in the NMB equation. Options:
#   "blended"      -> (3*input + output) / 4  per 1M tokens (CommandCode's blend)
#   "output"       -> output $/1M
#   "input"        -> input $/1M
#   "cost_per_task"-> cost of one reference task (see TASK profile below)
COST_METRIC = "blended"

# Latency handling: add a penalty term to NMB rather than hard-filtering, so slow
# models are priced down but not silently dropped (and missing latency data is not
# unfairly punished). CommandCode does not publish latency, so leave per-model
# latency as None and the term inert (mu=0) until we have our own measurements.
LATENCY_PENALTY_MU = 0.0  # dollars of NMB lost per (unit) of latency

# Reference "agent task" used for cost_per_task. Mirrors CommandCode's agent-loop
# assumption that most input is cache-hit, so effective input rate is
# (1-cache_hit)*input + cache_hit*cache_read.
TASK_INPUT_TOKENS = 250_000
TASK_OUTPUT_TOKENS = 12_000
TASK_CACHE_HIT_RATE = 0.70

# Blend weights for "blended" $/1M: (w_in*input + w_out*output) / (w_in + w_out)
BLEND_INPUT_WEIGHT = 3.0
BLEND_OUTPUT_WEIGHT = 1.0

USER_AGENT = "Mozilla/5.0 (smart-router-sample)"


# --------------------------------------------------------------------------- #
# Data model                                                                   #
# --------------------------------------------------------------------------- #


@dataclass
class Model:
    name: str
    slug: str = ""
    model_id: Optional[str] = None
    intelligence: Optional[float] = None
    coding_index: Optional[float] = None
    input_price: Optional[float] = None  # $/1M
    output_price: Optional[float] = None  # $/1M
    cache_read_price: Optional[float] = None  # $/1M
    cache_write_price: Optional[float] = None  # $/1M
    context_tokens: Optional[int] = None
    context_display: Optional[str] = None
    capabilities: Optional[str] = None
    supported_endpoints: list = field(default_factory=list)
    efforts: Optional[str] = None
    min_plan: Optional[str] = None
    best_for: Optional[str] = None
    latency: Optional[float] = None  # seconds; not published by CommandCode
    benchmarks: dict = field(default_factory=dict)

    # derived
    def cost_blended(self) -> Optional[float]:
        if self.input_price is None or self.output_price is None:
            return None
        w_in, w_out = BLEND_INPUT_WEIGHT, BLEND_OUTPUT_WEIGHT
        return (w_in * self.input_price + w_out * self.output_price) / (w_in + w_out)

    def agent_loop_input_cost(self) -> Optional[float]:
        if self.input_price is None:
            return None
        cr = self.cache_read_price if self.cache_read_price is not None else self.input_price
        hit = TASK_CACHE_HIT_RATE
        return (1.0 - hit) * self.input_price + hit * cr

    def cost_per_task(self) -> Optional[float]:
        if self.input_price is None or self.output_price is None:
            return None
        in_cost = self.agent_loop_input_cost() * (TASK_INPUT_TOKENS / 1e6)
        out_cost = self.output_price * (TASK_OUTPUT_TOKENS / 1e6)
        return in_cost + out_cost

    def cost_for_nmb(self) -> Optional[float]:
        if COST_METRIC == "blended":
            return self.cost_blended()
        if COST_METRIC == "output":
            return self.output_price
        if COST_METRIC == "input":
            return self.input_price
        if COST_METRIC == "cost_per_task":
            return self.cost_per_task()
        return self.cost_blended()

    def nmb(self, lam: float, mu: float) -> Optional[float]:
        if self.intelligence is None or self.cost_for_nmb() is None:
            return None
        penalty = 0.0
        if mu and self.latency is not None:
            penalty = mu * self.latency
        return (lam * self.intelligence) - self.cost_for_nmb() - penalty


# --------------------------------------------------------------------------- #
# Fetching                                                                     #
# --------------------------------------------------------------------------- #


def _http_get(url: str, headers: Optional[dict] = None, timeout: int = 30) -> str:
    hdr = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def load_env_file(path: str = ".env") -> dict:
    vals = {}
    if not os.path.exists(path):
        return vals
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def fetch_live_models(api_key: Optional[str]) -> dict:
    """Return norm(name) -> {id, supported_endpoints, context_length} from the API."""
    if not api_key:
        return {}
    try:
        body = _http_get(
            f"{API_BASE}/models", headers={"Authorization": f"Bearer {api_key}"}
        )
        data = json.loads(body)
    except Exception as exc:  # network/auth failure is non-fatal
        print(f"  [warn] live model list unavailable: {exc}", file=sys.stderr)
        return {}
    out = {}
    for m in data.get("data", []):
        out[norm_name(m.get("name", m.get("id", "")))] = {
            "id": m.get("id"),
            "supported_endpoints": m.get("supported_endpoints", []),
            "context_length": m.get("context_length"),
        }
    return out


def fetch_catalog_table() -> list[Model]:
    """Parse commandcode.ai/models HTML table -> list[Model] with intelligence+prices."""
    html = _http_get(MODELS_PAGE_URL)
    slug_to_name = _parse_jsonld_names(html)
    models = []
    for row in _table_rows(html):
        cells = row["cells"]
        if len(cells) < 7:
            continue
        slug = row["slug"]
        name = slug_to_name.get(slug) or _clean_name_cell(cells[0])
        intel = _parse_float(cells[2])
        ctx_disp = _strip_tags(cells[1]).strip()
        models.append(
            Model(
                name=name,
                slug=slug,
                intelligence=intel,
                context_display=ctx_disp,
                context_tokens=_parse_context(ctx_disp),
                input_price=_parse_price(cells[3]),
                output_price=_parse_price(cells[4]),
                cache_read_price=_parse_price(cells[5]),
                cache_write_price=_parse_price(cells[6]),
                capabilities=_parse_caps(cells[7]) if len(cells) > 7 else None,
            )
        )
    return models


def fetch_cost_metadata() -> dict:
    """Parse models.md -> norm(name) -> {id, efforts, min_plan, best_for}."""
    try:
        md = _http_get(MODELS_MD_URL)
    except Exception as exc:
        print(f"  [warn] models.md unavailable: {exc}", file=sys.stderr)
        return {}
    out = {}
    for line in md.splitlines():
        s = line.strip()
        if not s.startswith("| `"):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 6:
            continue
        mid = _first_backtick(cols[0])
        name = _strip_tags(cols[1])
        if not mid or not name:
            continue
        out[norm_name(name)] = {
            "id": mid,
            "efforts": cols[3] or None,
            "min_plan": cols[5] or None,
            "best_for": cols[6] if len(cols) > 6 else None,
        }
    return out


# --------------------------------------------------------------------------- #
# HTML / text helpers                                                          #
# --------------------------------------------------------------------------- #


def _strip_tags(html: str) -> str:
    txt = re.sub(r"<[^>]*>", " ", html)
    txt = (
        txt.replace("&amp;", "&")
        .replace("&#x27;", "'")
        .replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return re.sub(r"\s+", " ", txt).strip()


def _table_rows(html: str) -> list[dict]:
    start = html.find("<table")
    end = html.find("</table>", start)
    table = html[start:end] if start != -1 and end != -1 else html
    rows = []
    for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        row_html = rm.group(1)
        cells = [m.group(2) for m in re.finditer(r"<(td|th)[^>]*>(.*?)</\1>", row_html, re.S)]
        href = re.search(r'href="([^"]*)"', row_html)
        slug = ""
        if href:
            slug = href.group(1).rstrip("/").split("/")[-1]
        rows.append({"cells": [_strip_tags(c) for c in cells], "raw": row_html, "slug": slug})
    # drop the header row (its cells are <th> rather than <td>)
    return [r for r in rows if r["cells"] and not r["raw"].lstrip().startswith("<th")]


def _parse_jsonld_names(html: str) -> dict:
    """slug -> clean display name, from the itemListElement JSON-LD block."""
    slug_to_name = {}
    for m in re.finditer(
        r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S
    ):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        items = obj.get("itemListElement") or []
        for it in items:
            url = it.get("url", "")
            nm = it.get("name", "")
            if url and nm:
                slug = url.rstrip("/").split("/")[-1]
                slug_to_name[slug] = nm
    return slug_to_name


def _clean_name_cell(cell: str) -> str:
    # Names can carry appended noise like "Off-peak shown (17h/day) ...".
    return re.split(r"\s+Off-peak\b|\s+Decision model\b", cell)[0].strip()


def _parse_price(cell: str) -> Optional[float]:
    s = cell.strip()
    if not s or s in {"—", "-", "–"}:
        return None
    if s.lower().startswith("free"):
        return 0.0
    m = re.search(r"\$\s*([\d.]+)", s)
    return float(m.group(1)) if m else None


def _parse_float(cell: str) -> Optional[float]:
    s = cell.strip()
    if not s or "not yet scored" in s.lower() or s in {"—", "-", "–"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _parse_context(cell: str) -> Optional[int]:
    s = cell.strip().upper().replace(",", "")
    m = re.match(r"([\d.]+)\s*([KM])?", s)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    if unit == "K":
        val *= 1_000
    elif unit == "M":
        val *= 1_000_000
    return int(val)


def _parse_caps(cell: str) -> Optional[str]:
    s = cell.strip()
    if not s or s.startswith("+"):
        return None
    return s


def _first_backtick(s: str) -> Optional[str]:
    m = re.search(r"`([^`]+)`", s)
    return m.group(1) if m else None


def norm_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)  # drop "(latest)", "(exp)", etc.
    s = re.sub(r"\bfree\b", " ", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


# --------------------------------------------------------------------------- #
# GOAT-tier availability + adaptive tier banding                               #
# --------------------------------------------------------------------------- #

# Public plan order (cheapest -> most expensive): Go < GOAT < Pro < Max.
# A model is "available for the GOAT tier" when its cheapest serving plan is
# GOAT or lower (Go, GOAT, or free). Pro / Max-only models are excluded.
GOAT_MAX_PLAN_RANK = 2


def plan_rank(p: Optional[str]) -> Optional[int]:
    if not p:
        return None
    pl = p.lower()
    if "max" in pl:
        return 4
    if "pro" in pl:
        return 3
    if "goat" in pl:  # before "go", which is a substring of "goat"
        return 2
    if "go" in pl:
        return 1
    if "free" in pl:
        return 0
    return None


def is_goat_available(p: Optional[str]) -> bool:
    r = plan_rank(p)
    return r is not None and r <= GOAT_MAX_PLAN_RANK


# --------------------------------------------------------------------------- #
# Optional per-model enrichment (coding index + benchmark sub-scores)          #
# --------------------------------------------------------------------------- #

BENCH_LABELS = [
    "Coding index",
    "Long-context reasoning",
    "SciCode",
    "GPQA Diamond",
    "Terminal-Bench",
]


def _stat_after(txt: str, label: str, window: int = 32) -> Optional[float]:
    """Pull the bare number that follows `label` on a model page ('not yet scored' -> None)."""
    i = txt.find(label)
    if i == -1:
        return None
    seg = txt[i + len(label) : i + len(label) + window]
    if "not yet" in seg[:18]:
        return None
    m = re.search(r"\d+(?:\.\d+)?", seg)
    return float(m.group(0)) if m else None


def enrich_models(models: list[Model]) -> None:
    """Fill coding_index + benchmarks for each model from its /models/<slug> page."""
    for m in models:
        if not m.slug:
            continue
        try:
            html = _http_get(MODEL_PAGE_BASE + m.slug, timeout=20)
        except Exception:
            continue
        txt = _strip_tags(html)
        m.coding_index = _stat_after(txt, "Coding index")
        m.benchmarks = {lbl: _stat_after(txt, lbl) for lbl in BENCH_LABELS}
        m.benchmarks = {k: v for k, v in m.benchmarks.items() if v is not None}


# --------------------------------------------------------------------------- #
# Algorithm                                                                    #
# --------------------------------------------------------------------------- #


def pareto_frontier(models: list[Model]) -> tuple[list[Model], list[Model]]:
    """Return (frontier, dominated). Cost axis = cost_for_nmb(), y = intelligence."""
    scored = [m for m in models if m.intelligence is not None and m.cost_for_nmb() is not None]
    frontier, dominated = [], []
    for a in scored:
        ca, ia = a.cost_for_nmb(), a.intelligence
        is_dominated = False
        for b in scored:
            if b is a:
                continue
            cb, ib = b.cost_for_nmb(), b.intelligence
            if ib >= ia and cb <= ca and (ib > ia or cb < ca):
                is_dominated = True
                break
        (dominated if is_dominated else frontier).append(a)
    return frontier, dominated


def assign_tier(model: Model, floors: dict) -> Optional[str]:
    if model.intelligence is None:
        return None
    for t in TIERS:
        if model.intelligence >= floors[t["name"]]:
            return t["name"]
    return None


def iterative_nmb_select(pool: list[Model], lam: float, mu: float, top_n: int) -> list[dict]:
    """Pick best by NMB, remove it, repeat — yielding up to top_n ranked candidates."""
    remaining = list(pool)
    picks = []
    for rank in range(1, top_n + 1):
        scored = [(m, m.nmb(lam, mu)) for m in remaining]
        scored = [(m, s) for m, s in scored if s is not None]
        if not scored:
            break
        best, best_score = max(scored, key=lambda t: t[1])
        picks.append(
            {
                "rank": rank,
                "model": best,
                "nmb_at_selection": round(best_score, 4),
                "pool_size_at_selection": len(remaining),
            }
        )
        remaining = [m for m in remaining if m is not best]
    return picks


# --------------------------------------------------------------------------- #
# Output                                                                       #
# --------------------------------------------------------------------------- #


def _fmt_money(v: Optional[float]) -> str:
    return "—" if v is None else f"${v:,.4g}"


def _fmt_ctx(m: Model) -> str:
    return m.context_display or ("—" if m.context_tokens is None else f"{m.context_tokens:,}")


def model_stats_dict(m: Model, rank: int, nmb: Optional[float]) -> dict:
    return {
        "rank": rank,
        "name": m.name,
        "id": m.model_id,
        "base_name": (f"openai/{m.model_id}" if m.model_id else None),
        "slug": m.slug,
        "intelligence_index": m.intelligence,
        "coding_index": m.coding_index,
        "cost_blended_per_m": m.cost_blended(),
        "cost_per_task_usd": m.cost_per_task(),
        "input_per_m": m.input_price,
        "output_per_m": m.output_price,
        "cache_read_per_m": m.cache_read_price,
        "cache_write_per_m": m.cache_write_price,
        "context_tokens": m.context_tokens,
        "context_display": m.context_display,
        "capabilities": m.capabilities,
        "supported_endpoints": m.supported_endpoints,
        "efforts": m.efforts,
        "min_plan": m.min_plan,
        "best_for": m.best_for,
        "benchmarks": m.benchmarks,
        "latency_seconds": m.latency,
        "nmb_at_selection": nmb,
    }


def build_json(payload: dict) -> str:
    return json.dumps(payload, indent=2)


def build_markdown(payload: dict) -> str:
    L = []
    L.append("# Smart Router — Top Models per Tier\n")
    L.append(f"_Generated: {payload['generated_at']}_\n")
    L.append(
        f"**SOTA intelligence (best GOAT-available model):** {payload['sota_intelligence']}   "
        f"**Cost metric for NMB:** {payload['parameters']['cost_metric']}"
    )
    L.append("")
    f = payload.get("filters", {})
    L.append(
        f"_Filter: GOAT-tier plans only ({f.get('goat_available_scored', 0)} scored models); "
        f"non-GOAT and unscored models excluded._"
    )
    L.append("")
    L.append("**Capability tier floors** (fractions of SOTA; each tier topped up to 5):\n")
    L.append("| Tier | Floor (xSOTA) | Floor score | Genuine pool | Backfilled | lambda ($/point) |")
    L.append("|------|---------------|-------------|--------------|------------|------------------|")
    for t in payload["tiers"]:
        L.append(
            f"| {t['name']} | {t['floor_frac']:.2f}x | "
            f"{t['floor_intelligence']:.2f} | {t['pool_size']} | "
            f"{t['backfilled_count']} | {t['lam']:.2f} |"
        )
    L.append("")
    L.append(
        "> Tier is decided by CAPABILITY (intelligence vs SOTA using the floor fractions "
        "above): a Pro-capability model is never labelled Ultra. Within each tier, models "
        "are ranked by iterative NMB = (lambda x intelligence) - cost - (mu x latency): "
        "select the best, remove it, and repeat. A tier with fewer than 5 genuine members "
        "is backfilled with the best models from lower tiers, marked _(+Tier)_ = the tier "
        "that model truly belongs to. (* = global Pareto frontier.)"
    )
    L.append("")

    for t in payload["tiers"]:
        L.append(f"## {t['name']} tier\n")
        L.append(
            f"_Floor {t['floor_intelligence']:.2f} ({t['floor_frac']:.2f}x SOTA) - "
            f"{t['pool_size']} genuine models - {t['backfilled_count']} backfilled._\n"
        )
        if not t["candidates"]:
            L.append("_No qualifying models for this tier._\n")
            continue
        L.append(
            "| # | Model | Base name | Intel | Cod | Cost $/M (blend) | Cost/task | Input $/M | "
            "Output $/M | Cache rd $/M | Context | NMB | Plan |"
        )
        L.append(
            "|---|-------|-----------|-------|-----|------------------|-----------|-----------|"
            "------------|-------------|---------|-----|------|"
        )
        for c in t["candidates"]:
            star = " *" if c.get("global_pareto") else ""
            bf = c.get("backfilled_from")
            bf_mark = f" _(+{bf})_" if bf else ""
            cod = c["coding_index"]
            cod_s = f"{cod:.0f}" if isinstance(cod, (int, float)) else "—"
            base = c.get("base_name") or "—"
            L.append(
                f"| {c['rank']} | {c['name']}{star}{bf_mark} | `{base}` | {c['intelligence_index']} | {cod_s} | "
                f"{_fmt_money(c['cost_blended_per_m'])} | {_fmt_money(c['cost_per_task_usd'])} | "
                f"{_fmt_money(c['input_per_m'])} | {_fmt_money(c['output_per_m'])} | "
                f"{_fmt_money(c['cache_read_per_m'])} | {c['context_display'] or '—'} | "
                f"{c['nmb_at_selection']} | {c['min_plan'] or '—'} |"
            )
        L.append("")

    if payload.get("filters", {}).get("excluded_unscored"):
        L.append("## Not scored (excluded from ranking)\n")
        L.append(", ".join(payload["filters"]["excluded_unscored"]))
        L.append("")
    if payload.get("filters", {}).get("excluded_non_goat_scored"):
        L.append("## Scored but not on the GOAT plan (excluded)\n")
        L.append(", ".join(payload["filters"]["excluded_non_goat_scored"]))
        L.append("")

    L.append("---\n")
    L.append(
        f"Global Pareto frontier: **{payload['pareto_kept_count']}** efficient, "
        f"**{payload['pareto_dropped_count']}** dominated (advisory only). "
        f"Latency penalty mu = {payload['parameters']['latency_penalty_mu']} "
        f"(CommandCode does not publish latency, so the term is inert by default)."
    )
    return "\n".join(L)


def print_tables(payload: dict) -> None:
    for t in payload["tiers"]:
        print(
            f"\n=== {t['name']} tier  (floor {t['floor_intelligence']:.2f}, "
            f"lambda={t['lam']}, true pool={t['pool_size']}, "
            f"backfilled={t['backfilled_count']}) ==="
        )
        if not t["candidates"]:
            print("  (no qualifying models)")
            continue
        hdr = (
            f"{'#':>2} {'Model':<30}{'Base name (CommandCode)':<34}"
            f"{'Intel':>6} {'Cod':>5} {'Cost$/M':>9} {'Task$':>8} {'Ctx':>6} {'NMB':>9} {'Glob':>5}"
        )
        print(hdr)
        print("-" * len(hdr))
        for c in t["candidates"]:
            cod = c["coding_index"]
            cod_s = f"{cod:.0f}" if isinstance(cod, (int, float)) else "—"
            eff = "front" if c.get("global_pareto") else ""
            bf = c.get("backfilled_from")
            name_disp = c["name"] + (f" (+{bf})" if bf else "")
            base = c.get("base_name") or "—"
            print(
                f"{c['rank']:>2} {name_disp[:30]:<30}{base[:34]:<34}"
                f"{(c['intelligence_index'] or 0):>6.1f} "
                f"{cod_s:>5} "
                f"{(c['cost_blended_per_m'] or 0):>9.4f} "
                f"{(c['cost_per_task_usd'] or 0):>8.4f} "
                f"{(c['context_display'] or '—'):>6} "
                f"{(c['nmb_at_selection'] or 0):>9.2f} "
                f"{eff:>5}"
            )
        print("  ('+Tier' = backfilled from that tier to keep >=5; Glob 'front' = global Pareto)")


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Dynamic LLM tier router sample")
    ap.add_argument("--top", type=int, default=TOP_N, help="candidates per tier")
    ap.add_argument("--json", default="smart_router_output.json")
    ap.add_argument("--md", default="smart_router_output.md")
    ap.add_argument("--no-api", action="store_true", help="skip the live /models API call")
    ap.add_argument(
        "--enrich",
        action="store_true",
        help="fetch per-model pages for selected models to add coding index + benchmarks",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="capability tiers only, no backfill (tiers may show fewer than --top)",
    )
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    env = load_env_file(os.path.join(here, ".env"))
    api_key = os.environ.get("COMMANDCODE_API_KEY") or env.get("COMMANDCODE_API_KEY")

    print("Fetching model data...")
    live = {} if args.no_api else fetch_live_models(api_key)
    print(f"  live models (API): {len(live)}")
    models = fetch_catalog_table()
    print(f"  catalog table (intelligence+prices): {len(models)}")
    meta = fetch_cost_metadata()
    print(f"  cost metadata (models.md): {len(meta)}")

    # merge enrichment by normalized name
    for m in models:
        key = norm_name(m.name)
        if key in live:
            m.model_id = live[key]["id"]
            m.supported_endpoints = live[key]["supported_endpoints"]
            if live[key]["context_length"]:
                m.context_tokens = live[key]["context_length"]
        if key in meta:
            m.model_id = m.model_id or meta[key]["id"]
            m.efforts = meta[key]["efforts"]
            m.min_plan = meta[key]["min_plan"]
            m.best_for = meta[key]["best_for"]

    # --- Rule 1: only models available on the GOAT plan (and scored) ---------
    goat_scored = [
        m
        for m in models
        if m.intelligence is not None
        and m.cost_for_nmb() is not None
        and is_goat_available(m.min_plan)
    ]
    non_goat_scored = [
        m.name
        for m in models
        if m.intelligence is not None and not is_goat_available(m.min_plan)
    ]
    unscored = [m.name for m in models if m.intelligence is None]
    print(f"  GOAT-available scored models: {len(goat_scored)}")

    # Global Pareto is now ADVISORY (a flag), not a hard filter: hard-filtering
    # drops the pool below the >=5-per-tier rule. NMB ranking already places
    # dominated models after their dominators, so value ordering is preserved.
    gp_frontier, _gp_dom = pareto_frontier(goat_scored)
    global_set = {m.name for m in gp_frontier}
    print(f"  global Pareto frontier (advisory): {len(gp_frontier)}")

    sota = max((m.intelligence for m in goat_scored), default=0.0)

    # --- Rule 2: capability-relative tiers ----------------------------------
    # A model's tier is decided by its CAPABILITY (intelligence vs SOTA) using
    # the architecture's floor fractions. This is the correct classification:
    # a Pro-capability model is never labelled Ultra, etc.
    floors = {t["name"]: t["floor_frac"] * sota for t in TIERS}
    buckets = {t["name"]: [] for t in TIERS}
    for m in goat_scored:
        tier = assign_tier(m, floors)
        if tier:
            buckets[tier].append(m)

    # To keep the ">=5 candidates per tier" rule WITHOUT mis-classifying models,
    # a tier that has fewer than 5 genuine members is BACKFILLED with the
    # highest-NMB models from the tiers below it. Each backfilled entry records
    # the tier it truly belongs to, so a genuine tier model is always
    # distinguishable from a stretched option.
    tier_entries = []
    selected_models = []
    for i, t in enumerate(TIERS):
        lam = t["lam"]
        entries = [
            {"model": p["model"], "nmb": p["nmb_at_selection"], "backfilled_from": None}
            for p in iterative_nmb_select(buckets[t["name"]], lam, LATENCY_PENALTY_MU, args.top)
        ]
        if len(entries) < args.top and not args.strict:
            lower = [m for j in range(i + 1, len(TIERS)) for m in buckets[TIERS[j]["name"]]]
            need = args.top - len(entries)
            for p in iterative_nmb_select(lower, lam, LATENCY_PENALTY_MU, need):
                entries.append(
                    {
                        "model": p["model"],
                        "nmb": p["nmb_at_selection"],
                        "backfilled_from": assign_tier(p["model"], floors),
                    }
                )
        tier_entries.append((t, entries))
        selected_models.extend(e["model"] for e in entries)

    if args.enrich and selected_models:
        seen, uniq = set(), []
        for m in selected_models:
            if m.slug and m.slug not in seen:
                seen.add(m.slug)
                uniq.append(m)
        print(f"  enriching {len(uniq)} selected models (coding index + benchmarks)...")
        enrich_models(uniq)

    tiers_out = []
    for t, entries in tier_entries:
        candidates = []
        for rank, e in enumerate(entries, 1):
            d = model_stats_dict(e["model"], rank, e["nmb"])
            d["global_pareto"] = e["model"].name in global_set
            d["backfilled_from"] = e["backfilled_from"]
            candidates.append(d)
        tiers_out.append(
            {
                "name": t["name"],
                "floor_intelligence": floors[t["name"]],
                "floor_frac": t["floor_frac"],
                "lam": t["lam"],
                "pool_size": len(buckets[t["name"]]),
                "backfilled_count": sum(1 for e in entries if e["backfilled_from"]),
                "candidates": candidates,
            }
        )

    unranked = unscored

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sota_intelligence": sota,
        "cost_metric": COST_METRIC,
        "filters": {
            "goat_tier_only": True,
            "goat_available_scored": len(goat_scored),
            "excluded_non_goat_scored": non_goat_scored,
            "excluded_unscored": unranked,
        },
        "parameters": {
            "cost_metric": COST_METRIC,
            "latency_penalty_mu": LATENCY_PENALTY_MU,
            "top_n_per_tier": args.top,
            "min_per_tier": args.top,
            "task_input_tokens": TASK_INPUT_TOKENS,
            "task_output_tokens": TASK_OUTPUT_TOKENS,
            "task_cache_hit_rate": TASK_CACHE_HIT_RATE,
            "blend_weights": {"input": BLEND_INPUT_WEIGHT, "output": BLEND_OUTPUT_WEIGHT},
            "tier_lambda": {t["name"]: t["lam"] for t in TIERS},
        },
        "tiers": tiers_out,
        "pareto_kept_count": len(gp_frontier),
        "pareto_dropped_count": len(goat_scored) - len(gp_frontier),
        "global_frontier": [
            {"name": m.name, "intelligence": m.intelligence, "cost": m.cost_for_nmb()}
            for m in sorted(gp_frontier, key=lambda x: -(x.intelligence or 0))
        ],
    }

    with open(os.path.join(here, args.json), "w", encoding="utf-8") as fh:
        fh.write(build_json(payload))
    with open(os.path.join(here, args.md), "w", encoding="utf-8") as fh:
        fh.write(build_markdown(payload))

    print_tables(payload)
    print(f"\nWrote {args.json} and {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
