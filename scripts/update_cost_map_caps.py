#!/usr/bin/env python3
"""Derive real CommandCode output caps and update custom_cost_map.json.

Why this exists
---------------
LiteLLM's Smart Router (router_strategy/complexity_router.py) injects
``max_tokens = min(max_output_tokens across the tier's deployments)`` on every
routed request (``config.max_tokens_from_tier_model`` defaults to True). If the
cost map *overstates* a model's real output ceiling, that injected value is
rejected by the provider with HTTP 400 -- and because a 400 is non-retryable,
the router does NOT fail over to the next ``order``.

So the cost map's ``max_output_tokens`` for every deployment must be <= the
provider's real ceiling. This script probes the CommandCode API to find each
model's real ceiling and rewrites only the affected lines.

How caps are found (per model)
------------------------------
1. baseline request at max_tokens=100 -- if it fails, the model is "unavailable"
   (provider-side error unrelated to max_tokens) and is left untouched.
2. request at max_tokens=10,000,000 -- if accepted, the real cap is >= 10M, so the
   existing declared value is already safe and is left untouched.
3. otherwise, read the cap straight out of the provider's error message when it
   states one, and independently bisect the accept/reject boundary for an
   empirically-proven-accepted value. The final value is the largest candidate
   that passes an N-repeat accept check (guards against transient 403s).

Only ``max_output_tokens`` and ``max_tokens`` are changed; everything else,
including formatting, is preserved (no JSON re-dump).

Usage
-----
  # dry run against the deployments in config.yaml
  python scripts/update_cost_map_caps.py --config config.yaml

  # apply, for an explicit set of deployment keys
  python scripts/update_cost_map_caps.py --models openai/z-ai/glm-5.3-flash --write

  # every CommandCode entry in the cost map (slow: ~89 models)
  python scripts/update_cost_map_caps.py --all-commandcode --write
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

CC_SOURCE = "https://commandcode.ai/models"
BIG = 10_000_000
BISECT_HI = 2_000_000

HINT_PATTERNS = (
    r"must be between 0 and (\d+)",
    r"\[1,\s*(\d+)\]",
    r"limit of (\d+)",
    r"lower than (\d+)",
    r"max_tokens:\s*\d+\s*>\s*(\d+)",
)


def load_key(env_path):
    try:
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("COMMANDCODE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


def make_post(base_url, api_key):
    def post(path, payload, timeout=90):
        req = urllib.request.Request(
            base_url + path,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
                "User-Agent": "curl/8.5.0",
                "Accept": "*/*",
            },
            method="POST",
        )
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
            return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - network errors -> treat as failure
            return -1, str(e)

    return post


def extract_hint(body):
    for pat in HINT_PATTERNS:
        m = re.search(pat, body)
        if m:
            return int(m.group(1))
    return None


def endpoint_for(key):
    """Deployment key -> (path, provider_model_id) or None if not CommandCode."""
    if key.startswith("openai/"):
        return "/chat/completions", key[len("openai/"):]
    if key.startswith("anthropic/"):
        return "/messages", key[len("anthropic/"):]
    return None


def probe(key, post, reps, sleep):
    ep = endpoint_for(key)
    if ep is None:
        return {"key": key, "status": "skip", "cap": None, "note": "not an openai/anthropic key"}
    path, model = ep

    def call(mt, n):
        codes = []
        body = ""
        for _ in range(n):
            code, body = post(path, {"model": model, "max_tokens": mt,
                                     "messages": [{"role": "user", "content": "hi"}]})
            codes.append(code)
            time.sleep(sleep)
        return all(c == 200 for c in codes), body

    ok100, body100 = call(100, 1)
    if not ok100:
        return {"key": key, "status": "unavailable", "cap": None, "note": body100[:120]}

    ok_big, body_big = call(BIG, 1)
    if ok_big:
        return {"key": key, "status": "ok", "cap": None, "note": "accepts >=10M (declared value kept)"}

    # Prefer the provider's stated cap; verify it (some providers enforce
    # max_tokens + prompt <= context and so reject their own stated limit).
    hint = extract_hint(body_big)
    if hint:
        ok_hint, _ = call(hint, reps)
        if ok_hint:
            return {"key": key, "status": "ok", "cap": hint, "note": f"stated={hint}"}

    # Generic error -> bisect the accepted boundary.
    lo, hi, best = 1, BISECT_HI, 1
    while lo <= hi:
        mid = (lo + hi) // 2
        ok, _ = call(mid, 2)
        if ok:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    while best > 1 and not call(best, reps)[0]:
        best //= 2
    return {"key": key, "status": "ok", "cap": best,
            "note": ("stated rejected; " if hint else "") + f"bisect={best}"}


def rewrite_block(text, key, new_val):
    """Replace max_output_tokens / max_tokens inside key's block, preserving formatting."""
    anchor = '"%s": {' % key
    i = text.find(anchor)
    if i < 0:
        return text, False
    j = text.find("\n    },", i)
    end = j if j >= 0 else len(text)
    block = text[i:end]

    changed = False
    for field in ("max_output_tokens", "max_tokens"):
        pat = re.compile(r'(\n\s*"%s":\s*)([^,\n]+)(,)' % field)
        if pat.search(block):
            block = pat.sub(lambda m: m.group(1) + str(new_val) + m.group(3), block, count=1)
            changed = True
    if not changed:
        return text, False
    return text[:i] + block + text[end:], True


def collect_keys(args, cost_map):
    if args.models:
        return [k.strip() for k in args.models.split(",") if k.strip()]
    if args.all_commandcode:
        return [k for k, v in cost_map.items()
                if isinstance(v, dict) and v.get("source") == CC_SOURCE]
    keys = []
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML required for --config; otherwise pass --models or --all-commandcode")
    cfg = yaml.safe_load(open(args.config, encoding="utf-8")) or {}
    for dep in cfg.get("model_list", []):
        model = (dep.get("litellm_params") or {}).get("model")
        if model:
            keys.append(model)
    # de-dup, keep order
    return list(dict.fromkeys(keys))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.yaml", help="LiteLLM config to read deployments from")
    ap.add_argument("--cost-map", default="custom_cost_map.json")
    ap.add_argument("--env", default=".env")
    ap.add_argument("--models", help="comma-separated deployment keys (overrides --config)")
    ap.add_argument("--all-commandcode", action="store_true", help="probe every CommandCode entry")
    ap.add_argument("--base-url", default="https://api.commandcode.ai/provider/v1")
    ap.add_argument("--reps", type=int, default=3, help="accept check repeats (transient-error guard)")
    ap.add_argument("--sleep", type=float, default=0.15, help="seconds between API calls")
    ap.add_argument("--write", action="store_true", help="apply changes (default: dry run)")
    args = ap.parse_args()

    key = load_key(args.env)
    if not key:
        sys.exit("COMMANDCODE_API_KEY not found in %s" % args.env)
    post = make_post(args.base_url, key)

    text = open(args.cost_map, encoding="utf-8").read()
    try:
        cost_map = json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit("invalid cost map JSON: %s" % e)

    keys = collect_keys(args, cost_map)
    print("probing %d deployment(s); reps=%d; mode=%s\n" % (
        len(keys), args.reps, "WRITE" if args.write else "dry-run"))

    changes = []
    for k in keys:
        if k not in cost_map:
            print("%-45s SKIP (not in cost map)" % k)
            continue
        r = probe(k, post, args.reps, args.sleep)
        cur = cost_map[k].get("max_output_tokens")
        if r["status"] == "ok" and r["cap"] is not None and r["cap"] != cur:
            changes.append((k, cur, r["cap"]))
            print("%-45s %-10s %s -> %s   [%s]" % (k, r["status"], cur, r["cap"], r["note"]))
        elif r["status"] == "ok":
            print("%-45s %-10s kept %s   [%s]" % (k, r["status"], cur, r["note"]))
        else:
            print("%-45s %-10s (kept %s)   [%s]" % (k, r["status"], cur, r["note"]))

    if not changes:
        print("\nNo changes needed.")
        return
    for k, _old, new in changes:
        text, ok = rewrite_block(text, k, new)
        if not ok:
            print("WARNING: could not rewrite block for %s" % k)

    if args.write:
        open(args.cost_map, "w", encoding="utf-8", newline="\n").write(text)
        print("\nWrote %d change(s) to %s" % (len(changes), args.cost_map))
    else:
        print("\n%d change(s) proposed. Re-run with --write to apply." % len(changes))


if __name__ == "__main__":
    main()
