"""Self-contained HTML tier report (``output/tier-report.html``).

Rendered natively from the in-memory ``ScoreResult`` — the same object the
Markdown reports are built from — never by parsing Markdown. The output is a
single file with inline CSS and JS and no external references, so it opens
offline and survives being emailed. Charts are inline SVG generated here;
there is deliberately no chart library (a CDN would break the offline
guarantee).
"""

from __future__ import annotations

import html
import math
from typing import Any

from model_pipeline.emit.report import _canon_index
from model_pipeline.limits import (
    FLAG_OUTPUT_EQUALS_CONTEXT,
    FLAG_OUTPUT_NOT_BELOW_CONTEXT,
    FLAG_UNRESOLVED,
)
from model_pipeline.scoring.pipeline import ScoreResult

_LIMIT_HINTS = {
    FLAG_UNRESOLVED: "no catalog entry published an output limit; the value is left unset",
    FLAG_OUTPUT_EQUALS_CONTEXT: "catalog entry reports output == its own context window (likely copied)",
    FLAG_OUTPUT_NOT_BELOW_CONTEXT: "output limit is not smaller than the provider's context window",
}


def _e(value: Any) -> str:
    """HTML-escape one value (None renders as an em dash)."""
    if value is None:
        return "&mdash;"
    return html.escape(str(value), quote=True)


def _money(value: float | None) -> str:
    return "&mdash;" if value is None else f"${value:.4f}"


def _latency(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.1f}s"


def _kind(dep) -> str:
    if dep.is_pinned:
        return "pinned"
    if dep.is_backup:
        return "backup"
    return "primary"


def _low_conf_block(low_conf: list | None) -> str:
    rows = list(low_conf or [])
    if not rows:
        return ""
    shown = "".join(
        f"<li>{_e(getattr(m, 'provider', ''))}:{_e(getattr(m, 'model_id', ''))}"
        f" &rarr; {_e(getattr(m, 'canonical_slug', ''))}"
        f" ({float(getattr(m, 'confidence', 0.0)):.2f})</li>"
        for m in rows[:15]
    )
    more = f"<li>&hellip; and {len(rows) - 15} more</li>" if len(rows) > 15 else ""
    return (
        '<div class="banner"><strong>Warning:</strong> '
        f"{len(rows)} low-confidence mapping(s) need review in "
        "<code>output/mappings.csv</code> — the ranking above may misclassify them."
        f"<ul>{shown}{more}</ul></div>"
    )


def _tier_cards(result: ScoreResult) -> str:
    parts: list[str] = []
    for tier in result.tiers:
        rows: list[str] = []
        for d in tier.deployments:
            top = d.order == 1
            cls = ' class="top-pick"' if top else ""
            order = f"{d.order} &#9733;" if top else str(d.order)
            rows.append(
                f"<tr{cls}><td>{order}</td><td>{_e(d.display_name)}</td>"
                f"<td>{_e(d.provider)}</td><td><code>{_e(d.model_id)}</code></td>"
                f"<td data-v=\"{d.intelligence}\">{d.intelligence}</td>"
                f"<td data-v=\"{d.cost_per_task}\">{_money(d.cost_per_task)}</td>"
                f"<td>{_latency(d.latency_seconds)}</td>"
                f"<td data-v=\"{d.nmb:.6f}\">{d.nmb:.6f}</td>"
                f"<td>{_kind(d)}</td><td><code>{_e(d.api_base)}</code></td></tr>"
            )
        deps = "".join(rows)
        pinned = ""
        empty_row = '<tr><td colspan="10"><em>No qualifying models.</em></td></tr>'
        if tier.pinned:
            items = "".join(
                f"<li>{_e(slug)} (order {order})</li>"
                for slug, order in sorted(tier.pinned.items(), key=lambda kv: kv[1])
            )
            pinned = f"<p><strong>Pinned by config:</strong></p><ul>{items}</ul>"
        excluded = ""
        if tier.excluded_by_config:
            names = ", ".join(sorted(tier.excluded_by_config))
            excluded = f"<p><em>Excluded by config: {_e(names)}.</em></p>"
        parts.append(
            f'<section class="tier"><h2>{_e(tier.name)} &rarr; '
            f"<code>{_e(tier.model_group)}</code></h2>"
            f"<p>Floor {tier.floor_intelligence:.2f} ({tier.floor_frac:.2f}x SOTA) · "
            f"lambda {tier.lam} · rho {tier.rho} &rarr; mu {tier.mu:.5g} · "
            f"pool {tier.pool_size} · {len(tier.deployments)} deployments · "
            f"backups {tier.backup_count}</p>"
            f"{pinned}{excluded}"
            '<p class="note">&#9733; marks each tier&#39;s order-1 pick '
            "(the deployment the router tries first).</p>"
            '<table class="deps"><thead><tr><th>#</th><th>Model</th>'
            "<th>Provider</th><th>Model ID</th><th>Intel</th><th>Cost/task</th>"
            "<th>Latency</th><th>NMB</th><th>Kind</th><th>API base</th></tr></thead>"
            "<tbody>" + (deps or empty_row) + "</tbody></table></section>"
        )
    return "\n".join(parts)


def _model_index(result: ScoreResult) -> str:
    index = _canon_index(result)
    rows = []
    for slug, row in sorted(index.items(), key=lambda kv: -(kv[1]["intel"] or 0)):
        intel = "&mdash;" if row["intel"] is None else str(row["intel"])
        intel_v = "" if row["intel"] is None else str(row["intel"])
        cost_v = "" if row["cost"] is None else str(row["cost"])
        if row["frontier"] is None:
            pareto = "&mdash;"
        else:
            pareto = "frontier" if row["frontier"] else "dominated"
        # A dominated model's dominator (smarter AND cheaper) lives here so the
        # index answers "why is this only a backup?" without a second table.
        dom = result.dominators.get(slug)
        if dom:
            dom_slug, dom_intel, dom_cost = dom
            dom_name = index.get(dom_slug, {}).get("name", dom_slug)
            dominated_by = (
                f"{_e(dom_name)}<br><small>intel {_e(dom_intel)} · "
                f"{_money(dom_cost)}</small>"
            )
        else:
            dominated_by = "&mdash;"
        eligible = ", ".join(row["eligible"]) or "—"
        pinned = ", ".join(row["pinned"]) or "—"
        excluded = ", ".join(row["excluded"]) or "—"
        selected = ", ".join(row["selected"]) or "—"
        rows.append(
            "<tr>"
            f"<td>{_e(row['name'])}</td>"
            f'<td data-v="{intel_v}">{intel}</td>'
            f'<td data-v="{cost_v}">{_money(row["cost"])}</td>'
            f"<td>{pareto}</td>"
            f"<td>{dominated_by}</td>"
            f"<td>{_e(eligible)}</td>"
            f"<td>{_e(pinned)}</td>"
            f"<td>{_e(excluded)}</td>"
            f"<td>{_e(selected)}</td>"
            "</tr>"
        )
    return (
        '<section><h2>Model index</h2>'
        "<p>Every scored model, where it was eligible, and where it was selected. "
        "Type to filter; click a header to sort.</p>"
        '<input id="q" type="search" placeholder="Filter models…">'
        '<table id="index"><thead><tr><th>Model</th><th data-sort="n">Intel</th>'
        '<th data-sort="n">Best cost/task</th><th>Pareto</th>'
        "<th>Dominated by</th><th>Eligible tiers</th>"
        "<th>Pinned in</th><th>Excluded in</th><th>Selected in</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def _tier_rankings(result: ScoreResult) -> str:
    parts: list[str] = []
    for tier in result.tiers:
        mu = tier.mu
        selected = [r for r in tier.ranking if r.status != "cut"]
        cut = [r for r in tier.ranking if r.status == "cut"]

        def _row(r, cls="", mu=mu):
            if r.latency_seconds is None:
                latency, penalty = "unknown", "&mdash;"
            else:
                latency = f"{r.latency_seconds:.1f}s"
                penalty = f"{mu * r.latency_seconds:.2f}"
            result_txt = "cut" if r.status == "cut" else f"{r.status} · order {r.order}"
            providers = ", ".join(r.providers)
            pareto = "frontier" if r.on_frontier else "dominated"
            order = r.order or "&mdash;"
            return (
                f'<tr class="{cls}"><td>{order}</td>'
                f"<td>{_e(r.display_name)}</td>"
                f"<td>{_e(providers)}</td>"
                f"<td>{r.intelligence}</td>"
                f"<td>{_money(r.cost_per_task)}</td>"
                f"<td>{latency}</td><td>{penalty}</td>"
                f"<td>{r.nmb:.2f}</td>"
                f"<td>{pareto}</td>"
                f"<td>{result_txt}</td></tr>"
            )

        def _row_cls(r):
            return " top-pick" if r.status != "cut" and r.order == 1 else ""

        body = "".join(_row(r, _row_cls(r).strip()) for r in selected)
        if cut:
            body += (
                '<tr class="cut-line"><td colspan="10">'
                f"cut line — top-{result.parameters['top_k_per_tier']} above, "
                f"{len(cut)} below</td></tr>"
            )
            body += "".join(_row(r, "cut") for r in cut)
        if not tier.ranking:
            body = '<tr><td colspan="10"><em>No eligible models.</em></td></tr>'
        parts.append(
            f"<details><summary><strong>{_e(tier.name)}</strong> &rarr; "
            f"<code>{_e(tier.model_group)}</code> — {len(selected)} selected, "
            f"{len(cut)} cut</summary>"
            "<p>Scored models — ranked by NMB, frontier (primary) candidates first, "
            "then dominated (backup) candidates.</p>"
            '<table class="rank"><thead><tr><th>#</th><th>Model</th>'
            "<th>Provider(s)</th><th>Intel</th><th>Cost/task</th><th>Latency</th>"
            "<th>Penalty</th><th>NMB</th><th>Pareto</th><th>Result</th>"
            f"</tr></thead><tbody>{body}</tbody></table></details>"
        )
    return "<section><h2>Per-tier rankings</h2>" + "\n".join(parts) + "</section>"


def _pareto_points(result: ScoreResult) -> list[dict]:
    """One plottable point per scored model, including its dominator."""
    index = _canon_index(result)
    pts: list[dict] = []
    for slug, row in index.items():
        if row["intel"] is None or row["cost"] is None:
            continue
        dom = result.dominators.get(slug)
        dom_name = ""
        dom_intel = None
        dom_cost = None
        if dom:
            dom_slug, dom_intel, dom_cost = dom
            dom_name = index.get(dom_slug, {}).get("name", dom_slug)
        pts.append(
            {
                "slug": slug,
                "name": row["name"],
                "intel": row["intel"],
                "cost": row["cost"],
                "frontier": bool(row["frontier"]),
                "dom": dom_name,
                "dom_intel": dom_intel,
                "dom_cost": dom_cost,
            }
        )
    return pts


def _f1(value: float) -> str:
    """One-decimal SVG coordinate (f-string format specs stay Python 3.10-safe)."""
    return f"{value:.1f}"


def _g(value: float) -> str:
    """Compact tick label."""
    return f"{value:g}"


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _place_labels(
    frontier: list[dict],
    x_of,
    y_of,
    bounds: tuple[float, float, float, float],
) -> list[dict]:
    """Place frontier labels without collisions.

    Each label tries a grid of positions around its point and takes the first
    that does not overlap an already-placed label or leave the plot area.
    """
    left, top, right, bottom = bounds
    placed: list[tuple[float, float, float, float]] = []
    out: list[dict] = []
    for p in frontier:
        x, y = x_of(p), y_of(p)
        width = 6.0 * len(p["name"]) + 8
        height = 13.0
        candidates = []
        for dy in (-8, 18, -26, 36, -44, 54):
            candidates.append((x + 10, y + dy))
            candidates.append((x - width - 10, y + dy))
        chosen = None
        for cx, cy in candidates:
            if cx < left or cx + width > right or cy - height < top or cy + 4 > bottom:
                continue
            box = (cx, cy - height, cx + width, cy + 4)
            if all(not _overlap(box, other) for other in placed):
                chosen = (cx, cy, box)
                break
        if chosen is None:
            chosen = (candidates[0][0], candidates[0][1],
                      (candidates[0][0], candidates[0][1] - height,
                       candidates[0][0] + width, candidates[0][1] + 4))
        cx, cy, box = chosen
        placed.append(box)
        out.append({"name": p["name"], "x": cx, "y": cy, "px": x, "py": y})
    return out


def _pareto_svg(result: ScoreResult) -> str:
    """Interactive cost-vs-intelligence scatter with the frontier drawn.

    Both axes increase in their natural direction: cost to the right (log
    scale) and intelligence upward, so an efficient model sits up and to the
    left. Models costing $0 cannot sit on a log axis, so they are drawn as
    diamonds pinned to the left edge. Hover details (including a dominated
    model's dominator) are supplied by the page's inline JS through the
    ``data-*`` attributes on each hit area.
    """
    pts = _pareto_points(result)
    if not pts:
        return "<p><em>No scored models to chart.</em></p>"

    width, height = 960, 560
    ml, mr, mt, mb = 90, 30, 30, 64
    iw, ih = width - ml - mr, height - mt - mb

    positive = [p["cost"] for p in pts if p["cost"] > 0]
    if positive:
        l0, l1 = math.log10(min(positive)), math.log10(max(positive))
    else:
        l0, l1 = 0.0, 1.0
    if l0 == l1:
        l0, l1 = l0 - 0.5, l1 + 0.5
    edge = (l1 - l0) * 0.04
    l0, l1 = l0 - edge, l1 + edge

    intels = [p["intel"] for p in pts]
    i0, i1 = min(intels), max(intels)
    pad = (i1 - i0) * 0.05 or 0.5
    i0, i1 = i0 - pad, i1 + pad

    def _x(cost: float) -> float:
        if cost <= 0:
            return ml + 3
        return ml + (math.log10(cost) - l0) / (l1 - l0) * iw

    def _y(intel: float) -> float:
        return mt + (i1 - intel) / (i1 - i0) * ih

    grid: list[str] = []
    ticks = 6
    for i in range(ticks):
        intel = i0 + (i1 - i0) * i / (ticks - 1)
        y = _y(intel)
        label = _g(intel)
        grid.append(
            '<line class="grid" x1="' + str(ml) + '" y1="' + _f1(y)
            + '" x2="' + str(ml + iw) + '" y2="' + _f1(y) + '"/>'
            + '<text class="tick" x="' + str(ml - 8) + '" y="' + _f1(y + 4)
            + '" text-anchor="end">' + label + "</text>"
        )
    decade = math.floor(l0)
    while decade <= math.ceil(l1):
        if l0 <= decade <= l1:
            x = _x(10.0**decade)
            label = "$" + _g(10.0**decade)
            grid.append(
                '<line class="grid" x1="' + _f1(x) + '" y1="' + str(mt)
                + '" x2="' + _f1(x) + '" y2="' + str(mt + ih) + '"/>'
                + '<text class="tick" x="' + _f1(x) + '" y="' + str(mt + ih + 22)
                + '" text-anchor="middle">' + label + "</text>"
            )
        decade += 1

    frontier = sorted(
        [p for p in pts if p["frontier"]], key=lambda p: p["cost"]
    )
    line = ""
    if len(frontier) >= 2:
        coords = " ".join(
            _f1(_x(p["cost"])) + "," + _f1(_y(p["intel"]))
            for p in frontier
        )
        line = '<polyline class="frontier-line" points="' + coords + '"/>'

    shapes: list[str] = []
    hits: list[str] = []
    for p in pts:
        x, y = _x(p["cost"]), _y(p["intel"])
        xs, ys = _f1(x), _f1(y)
        cost_txt = "FREE" if p["cost"] <= 0 else _money(p["cost"])
        attrs = (
            ' data-name="' + _e(p["name"]) + '"'
            + ' data-intel="' + _e(p["intel"]) + '"'
            + ' data-cost="' + _e(cost_txt) + '"'
            + ' data-free="' + ("1" if p["cost"] <= 0 else "0") + '"'
        )
        if p["dom"]:
            attrs += (
                ' data-dom="' + _e(p["dom"]) + '"'
                + ' data-domintel="' + _e(p["dom_intel"]) + '"'
                + ' data-domcost="' + _e(_money(p["dom_cost"])) + '"'
            )
        if p["cost"] <= 0:
            r = 7
            points = (
                xs + "," + _f1(y - r) + " "
                + _f1(x + r) + "," + ys + " "
                + xs + "," + _f1(y + r) + " "
                + _f1(x - r) + "," + ys
            )
            shapes.append('<polygon class="free" points="' + points + '"/>')
        else:
            cls = "pt front" if p["frontier"] else "pt dom"
            shapes.append(
                '<circle class="' + cls + '" cx="' + xs + '" cy="' + ys
                + '" r="5"/>'
            )
        hits.append(
            '<circle class="hit" cx="' + xs + '" cy="' + ys + '" r="10"'
            + attrs + "/>"
        )

    labels = _place_labels(
        frontier,
        lambda p: _x(p["cost"]),
        lambda p: _y(p["intel"]),
        (ml, mt, ml + iw, mt + ih),
    )
    label_parts: list[str] = []
    for item in labels:
        leader = ""
        if abs(item["x"] - item["px"]) > 14 or abs(item["y"] - item["py"]) > 18:
            lx = item["px"] + (5 if item["x"] > item["px"] else -5)
            ly = item["py"]
            ax = item["x"] if item["x"] > item["px"] else item["x"] + 6.0 * len(item["name"]) + 8
            ay = item["y"] - 4
            leader = (
                '<line class="leader" x1="' + _f1(lx) + '" y1="' + _f1(ly)
                + '" x2="' + _f1(ax) + '" y2="' + _f1(ay) + '"/>'
            )
        label_parts.append(
            leader
            + '<text class="lbl" x="' + _f1(item["x"]) + '" y="'
            + _f1(item["y"]) + '">' + _e(item["name"]) + "</text>"
        )

    xlabel = (
        '<text class="axis" x="' + str(ml + iw / 2) + '" y="' + str(height - 12)
        + '" text-anchor="middle">cost/task ($) — log scale, right = more expensive</text>'
    )
    ylabel = (
        '<text class="axis" x="24" y="' + str(mt + ih / 2)
        + '" text-anchor="middle" transform="rotate(-90 24,'
        + str(mt + ih / 2) + ')">intelligence (higher = smarter)</text>'
    )
    return (
        '<div id="chart"><svg viewBox="0 0 ' + str(width) + " " + str(height)
        + '" role="img" aria-label="Pareto frontier chart">'
        + "".join(grid) + line + "".join(shapes) + "".join(hits)
        + "".join(label_parts) + xlabel + ylabel + "</svg>"
        + '<div id="tip" role="status"><span id="tip-name"></span>'
        + '<span id="tip-meta"></span><span id="tip-dom"></span></div>'
        + '<p class="legend"><span class="sw front"></span>frontier · '
        + '<span class="sw dom"></span>dominated · '
        + '<span class="sw free"></span>free ($0, left edge) · '
        + "up and to the left is better · "
        + "hover a point for details, including the model that dominates it</p>"
        + "</div>"
    )


def _pareto_section(result: ScoreResult) -> str:
    return (
        '<section id="pareto"><h2>Pareto frontier</h2>'
        f"<p><strong>{result.pareto_kept}</strong> efficient models on the frontier; "
        f"<strong>{result.pareto_dropped}</strong> dominated "
        "(another model is both smarter and cheaper). "
        "The axes read normally: cost rises to the right, intelligence rises upward, "
        "so the best trade-offs sit in the top-left corner.</p>"
        f"{_pareto_svg(result)}</section>"
    )


def _excluded_section(result: ScoreResult) -> str:
    excluded = "".join(
        f"<p><strong>{_e(reason)}</strong> ({len(items)}): "
        f"{_e(', '.join(items[:20]))}{' …' if len(items) > 20 else ''}</p>"
        for reason, items in result.excluded.items()
    )
    return f"<section><h2>Excluded</h2>{excluded or '<p>None.</p>'}</section>"


def _limits_section(result: ScoreResult) -> str:
    limits = "".join(
        f"<p><strong>{_e(flag)}</strong> ({len(items)}) — {_e(_LIMIT_HINTS[flag])}: "
        f"{_e(', '.join(sorted(items)[:20]))}"
        f"{' …' if len(items) > 20 else ''}</p>"
        for flag in _LIMIT_HINTS
        for items in [[k for k, v in result.limit_flags.items() if flag in v]]
        if items
    ) or "<p>Every fetched model resolved an output limit.</p>"
    return f"<section><h2>Token limits</h2>{limits}</section>"


def _warnings_section(result: ScoreResult, low_conf: list | None) -> str:
    """All data-quality warnings, grouped at the bottom of the page."""
    block = _low_conf_block(low_conf)
    pin_warnings = (
        "<ul>" + "".join(f"<li>{_e(w)}</li>" for w in result.pin_warnings) + "</ul>"
        if result.pin_warnings
        else ""
    )
    if not block and not pin_warnings:
        return ""
    return (
        '<section id="warnings"><h2>Warnings</h2>'
        f"{block}{pin_warnings}</section>"
    )


_CSS = (
    "body{font-family:system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em}"
    "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.9em}"
    "th,td{border:1px solid #ccc;padding:.35em .6em;text-align:left}"
    "th{background:#f0f0f0;cursor:default}th[data-sort]{cursor:pointer}"
    "tbody tr:nth-child(even){background:#fafafa}"
    "tr.cut{opacity:.6}.cut-line td{background:#ffe9a8;font-weight:bold;text-align:center}"
    "tbody tr.top-pick td{background:#e6ffed;font-weight:600}"
    "tbody tr.top-pick td:first-child{border-left:4px solid #1a7f37}"
    ".banner{background:#fff3cd;border:1px solid #d9a800;padding:1em;margin:1em 0}"
    "details{margin:1em 0;border:1px solid #ddd;padding:.5em 1em}"
    "summary{cursor:pointer}#q{width:100%;padding:.5em;margin:.5em 0}"
    "nav a{margin-right:1em}code{font-size:.85em}.note{font-size:.85em;color:#555}"
    "svg{width:100%;height:auto;border:1px solid #ddd;background:#fff}"
    ".grid{stroke:#e5e5e5}.tick{font-size:11px;fill:#555}"
    ".axis{font-size:12px;fill:#333}"
    ".pt.front{fill:#1a7f37;stroke:#0d5c26;stroke-width:1.5}"
    ".pt.dom{fill:#fff;stroke:#888;stroke-width:1.5}"
    ".free{fill:#8250df;stroke:#5a32a3;stroke-width:1.5}"
    ".frontier-line{fill:none;stroke:#1a7f37;stroke-width:2;stroke-dasharray:6 3}"
    ".lbl{font-size:11px;fill:#333;pointer-events:none}"
    ".leader{stroke:#999;stroke-width:.7;pointer-events:none}"
    ".hit{fill:transparent;cursor:pointer}"
    ".hit:hover{fill:rgba(26,127,55,.15);stroke:#1a7f37;stroke-width:1}"
    ".legend{font-size:.85em;color:#555}"
    ".sw{display:inline-block;width:.8em;height:.8em;border-radius:50%;margin:0 .3em 0 1em;vertical-align:baseline}"
    ".sw.front{background:#1a7f37}.sw.dom{background:#fff;border:1px solid #888}"
    ".sw.free{background:#8250df;border-radius:0}"
    "#tip{display:none;position:fixed;z-index:20;max-width:340px;background:#222;color:#fff;"
    "padding:.5em .7em;border-radius:6px;font-size:.85em;pointer-events:none;line-height:1.4}"
    "#tip span{display:block}#tip-name{font-weight:bold}"
    "#tip-dom{color:#ffd479;display:none}"
)


_JS = (
    "var q=document.getElementById('q');"
    "q.addEventListener('input',function(){"
    "var s=q.value.toLowerCase();"
    "document.querySelectorAll('#index tbody tr').forEach(function(r){"
    "r.style.display=r.textContent.toLowerCase().includes(s)?'':'none';});});"
    "document.querySelectorAll('#index th[data-sort]').forEach(function(h){"
    "h.addEventListener('click',function(){"
    "var t=h.closest('table'),b=t.tBodies[0],i=[...h.parentNode.children].indexOf(h);"
    "var asc=h.dataset.asc!=='1';h.dataset.asc=asc?'1':'0';"
    "[...b.rows].sort(function(a,c){"
    "var x=a.cells[i].dataset.v||a.cells[i].textContent;"
    "var y=c.cells[i].dataset.v||c.cells[i].textContent;"
    "var nx=parseFloat(x),ny=parseFloat(y);"
    "if(!isNaN(nx)&&!isNaN(ny)&&x!==''&&y!=='')return asc?nx-ny:ny-nx;"
    "return asc?x.localeCompare(y):y.localeCompare(x);}"
    ").forEach(function(r){b.appendChild(r);});});});"
    "var tip=document.getElementById('tip'),tipName=document.getElementById('tip-name'),"
    "tipMeta=document.getElementById('tip-meta'),tipDom=document.getElementById('tip-dom');"
    "function placeTip(ev){tip.style.left=(ev.clientX+16)+'px';tip.style.top=(ev.clientY+16)+'px';}"
    "document.querySelectorAll('#chart .hit').forEach(function(el){"
    "el.addEventListener('mousemove',function(ev){"
    "var d=el.dataset;tipName.textContent=d.name;"
    "tipMeta.textContent='intel '+d.intel+' · '+(d.free==='1'?'free ($0/task)':d.cost+'/task');"
    "if(d.dom){tipDom.textContent='dominated by '+d.dom+' (intel '+d.domintel+' · '+d.domcost+'/task)';"
    "tipDom.style.display='block';}else{tipDom.style.display='none';}"
    "tip.style.display='block';placeTip(ev);});"
    "el.addEventListener('mouseleave',function(){tip.style.display='none';});});"
)


def build_html(result: ScoreResult, low_conf: list | None = None) -> str:
    """Render the full ranking story as one self-contained HTML page."""
    methods = ", ".join(f"{k}={v}" for k, v in result.cost_methods.items())
    has_warnings = bool(result.pin_warnings) or bool(low_conf)
    warnings_link = '<a href="#warnings">Warnings</a>' if has_warnings else ""
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>Model pipeline — tier report ({_e(result.generated_at)})</title>"
        f"<style>{_CSS}</style></head><body>"
        "<h1>Model pipeline — tier report</h1>"
        f"<p><em>Generated: {_e(result.generated_at)}</em></p>"
        f"<p><strong>SOTA intelligence:</strong> {result.sota_intelligence}</p>"
        f"<p><strong>Cost methods:</strong> {_e(methods)}</p>"
        "<nav><a href=\"#pareto\">Pareto chart</a><a href=\"#tiers\">Tiers</a>"
        "<a href=\"#index-nav\">Model index</a><a href=\"#rankings\">Rankings</a>"
        f"{warnings_link}</nav>"
        f"{_pareto_section(result)}"
        f'<section id="tiers"><h2>Tiers</h2>{_tier_cards(result)}</section>'
        f'<section id="index-nav">{_model_index(result)}</section>'
        f'<section id="rankings">{_tier_rankings(result)}</section>'
        f"{_excluded_section(result)}"
        f"{_limits_section(result)}"
        f"{_warnings_section(result, low_conf)}"
        f"<script>{_JS}</script></body></html>"
    )


def write_html(path, result: ScoreResult, low_conf: list | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html(result, low_conf), encoding="utf-8")
