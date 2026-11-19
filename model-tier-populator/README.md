# model-pipeline

A reusable pipeline that keeps a [LiteLLM](https://docs.litellm.ai/) router
stocked with an **up-to-date, provider-specific tier list of models**.

It fetches the model catalogs of multiple LLM providers, de-duplicates them to a
single canonical identity, scores each model by intelligence and cost-efficiency,
ranks them into tiers, and pushes the result into LiteLLM's database via its
management API — no config edits, no restarts.

```
  providers            canonical hub        score & rank        populate
  ─────────            ─────────────        ────────────        ────────
  CommandCode  ──┐                          Pareto (advisory)   LiteLLM
  OpenCode     ──┼──▶ Artificial Analysis ──▶ SOTA tiers   ──▶  /model/new
  OpenRouter   ──┘    (intelligence+price)   NMB top-K          (idempotent)
                 └──▶ Jev classifier                     
                      (name matching)
```

Tiers map to LiteLLM model groups that a complexity router can route to:

| Tier | LiteLLM model group |
|------|---------------------|
| Ultra | `ultra-tier` |
| Pro | `pro-tier` |
| Flash | `flash-tier` |
| Flash Lite | `flash-lite-tier` |

## Why

Editing `config.yaml` and restarting LiteLLM to change models is slow and manual.
This pipeline makes the tier list **programmatic, repeatable, and schedulable**,
and keeps it in the database where it can be updated without a restart.

## How it works (three independent phases)

```
  fetch  ──▶  output/mappings.csv   (review gate)   ──▶  score  ──▶  output/tier-output.json   (review gate)  ──▶  populate
```

Each phase reads/writes files, so any phase can be re-run on its own:

- **fetch** — pull provider catalogs + prices, drop models your subscription
  plan cannot serve, map each model to an Artificial Analysis canonical identity
  (exact match first, then the Jev classifier), and write `mappings.csv` for a
  human to review/fix.
- **score** — compute a cost-per-task per model, mark the Pareto frontier, assign
  SOTA-relative tiers, rank by NMB, and write `tier-output.json` plus the
  readable reports (`tier-output.md`, `tier-ranking.md`, `tier-report.html`).
- **populate** — diff the desired tier list against LiteLLM's current models and
  apply only the changes. Re-running is safe (idempotent).

Two combined verbs: `run` (fetch → score → populate) and `refresh`
(fetch → score only — it never contacts LiteLLM, so it works with no LiteLLM
server or master key). Both stop at the first failing phase. The one-click
launcher runs `refresh`, opens the report, then offers the guarded
`populate --interactive` step described below.

## Requirements

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/)
- A running LiteLLM proxy with `store_model_in_db: true` (already set in this repo)
  — only needed for `populate`; `fetch`/`score`/`refresh` and the HTML report work without it
- Keys in the **repo-root `.env`** (`D:\Softwares\LiteLLMAiRouter\.env`):

  | Key | Used for |
  |-----|----------|
  | `COMMANDCODE_APIS` / `OPENCODE_APIS` / `OPEN_ROUTER_APIS` | JSON arrays of raw keys per provider. `fetch` tries them in order; `populate` publishes one deployment per key. The legacy single-key `*_API_KEY` variables still work (they publish `os.environ/NAME`). |
  | `JEV_API_KEY` | Jev name matching (a CommandCode key; the same variable feeds the router classifier in the container) |
  | `ARTIFICIAL_ANALYSIS_API_KEY` | canonical identity + intelligence scores |
  | `LITELLM_MASTER_KEY` | LiteLLM management API |

  Provider keys are read from the populator's `.env` and sent as raw keys during
  `populate`, so the LiteLLM container needs no provider variables at all. Keep
  a legacy single key only if you still use the `os.environ/...` form.

## Quick start

Run from the `model-pipeline/` directory:

```bash
uv sync                                   # install deps (once)

uv run model-pipeline refresh             # refresh + score in one go -> output/tier-report.html
#   or double-click refresh-and-open.bat  # same refresh, opens the report, then offers an optional populate preview
```

`refresh` runs `fetch` then `score` and never touches LiteLLM — it is the
one-click path for "what are the best models on my provider today". No
LiteLLM server or master key is needed; the only secrets used are the
provider + Artificial Analysis keys.

`populate --interactive` is the guarded apply step. It prints the configured
server (base URL/host, readiness, database, LiteLLM version), the current
pipeline-managed model counts per tier group, and the full diff, then asks one
question. Only `y`/`yes` applies; anything else leaves LiteLLM unchanged.
`populate` without the flag still applies immediately (for automation), and
`populate --dry-run` previews without prompting. The launcher runs the
interactive form after opening the report.

For the gated manual workflow:

```bash
uv run model-pipeline fetch               # 1. fetch + dedup  -> output/mappings.csv
#   review output/mappings.csv ; fix any 'override' cells for low-confidence rows

uv run model-pipeline score               # 2. rank           -> output/tier-output.json + output/tier-report.html
#   review output/tier-output.json

uv run model-pipeline populate --dry-run  # 3a. preview the diff
uv run model-pipeline populate            # 3b. apply to LiteLLM
```

`score` also writes `output/suggested_router_config.yaml`. Review it and copy
its `router_settings` into the root `config.yaml` (latency routing, per-order
retry policy, and the cooldown/walk-time guidance). The pipeline never edits the
root config.

## TLS note — endpoint is signed by an internal CA

The LiteLLM endpoint in `config.yaml` (`litellm.base_url`) is fronted by nginx
with a certificate issued by the company's internal CA
(`CN=boardpac-BOARDPACDC1-CA`). That CA is not in the public root store Python
ships with, so verification fails against `certifi`:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
self-signed certificate in certificate chain (_ssl.c:1032)
```

That message is literal: the server sends **its own root as a chain
certificate**, and the last cert in the chain is self-signed and not known to
Python. (A public CA never sends its root in the chain; an internal CA
frequently does.)

The pipeline always verifies TLS and has no off switch; instead, Python trusts
an explicit certificate bundle via `SSL_CERT_FILE`. That variable **replaces**
the CA bundle (it does not add to it), so the bundle must also contain the
normal public roots — otherwise the provider fetches fail too.

- `certs/company-root-ca.pem` — the endpoint's **issuing CA**, taken from the
  live handshake.
- `certs/ca-bundle.pem` — certifi's public roots **plus** that CA. This is the
  file to use.

In PowerShell, set it in the session **before** any command that talks to the
network (`fetch`, `run`, `populate`):

```powershell
$env:SSL_CERT_FILE = "$PWD\certs\ca-bundle.pem"
```

`refresh-and-open.bat` sets it for you when the bundle exists.

Rebuild the bundle after a cert change or a `uv sync` that updates certifi:

```powershell
.venv\Scripts\python.exe rebuild_ca_bundle.py
```

The script re-reads the issuing CA from the live TLS handshake, rewrites
`certs/company-root-ca.pem`, and regenerates `certs/ca-bundle.pem`.

Open items (infrastructure, not pipeline): stop sending the root in the served
chain, deploy the internal CA to client machines (GPO), and exclude the host
from antivirus TLS inspection — interception replaces the certificate with one
signed by a local "SSL Filter CA", which is what makes browser behaviour differ
between machines.


## Outputs (`output/`)

| File | What it is |
|------|------------|
| `mappings.csv` | provider model -> canonical model, with method + confidence + `override` column |
| `models_snapshot.json` | fetched provider models + normalized prices (lets `score` run offline) |
| `fetch-census.json` | per-provider advertised/extracted counts and the model IDs dropped before dedup |
| `aa_snapshot.json` | cached Artificial Analysis models list |
| `suggested_config.yaml` | task-profile values suggested from provider docs (advisory) |
| `tier-output.json` | **the tier list** — self-contained; all `populate` needs. Each deployment carries its credential slot/fingerprint, capability source/flags, and full LiteLLM payload |
| `tier-output.md` | same result as a readable table, with a key count per model/provider and capability warnings |
| `tier-ranking.md` | full ranking story: every scored model, per-tier NMB rankings with the cut line, Pareto dominators, exclusions, token-limit and capability flags |
| `tier-report.html` | same story as a single self-contained page (no network needed), with an interactive Pareto chart and highlighted per-tier top picks — written by every `score`/`refresh`/`run`; open it in any browser, no LiteLLM required |
| `suggested_router_config.yaml` | reviewable `router_settings` for same-order latency-pool failover; copy into the root `config.yaml`, never applied automatically |

## Configuration

Everything lives in `config.yaml` - task profile, NMB tuning
(tier lambdas/floors, top-K), pricing policy, providers, exclusions, pins, and the
tier→model-group mapping. Each setting has an inline comment explaining what it
is and when to change it. Nothing is hardcoded in the source.

`config.yaml` is gitignored: it is personal tuning that differs per person. The
tracked template is [`config.example.yaml`](config.example.yaml) - copy it to
`config.yaml` to get started. Every key, its shape, and its possible values are
documented inline there; keep the template in sync when you add a key.

`exclude` has two scopes: `patterns` drops a model from every tier before
ranking, while `tiers` drops it from one named tier only and leaves it available
to the others. Global patterns always win.

`pins.tiers` is the opposite control: an ordered list of canonical slugs
force-included at the top of a tier, ahead of NMB selection. Pins bypass the
tier's intelligence floor, consume top-K slots, and never override an exclusion.
Unknown, duplicate, or excluded slugs produce warnings and are skipped.

`providers.<name>.api_keys_env` names one env var holding a JSON array of keys.
The pipeline tries them in order for `/models` and publishes one deployment per
key at the same order; a failed key is benched by per-deployment
`allowed_fails: 0` and retried on a sibling. `litellm.num_retries`,
`allowed_fails`, `cooldown_time`, `timeout`, and `lowest_latency_buffer` are the
bootstrap values written into every deployment and the suggested router block.
Capabilities (`supports_vision`, `supports_audio_output`, `modalities`,
`supports_reasoning`, `reasoning_effort_levels`, per-level flags) come from the
provider's own models.dev entry; unknown fields are omitted and flagged.

`pricing.time_price_mode` chooses how time-of-day prices are collapsed:
`today` (weighted over today's slice of the active window — a weekday-only
schedule comes out as plain off-peak on a weekend run), `average` (the whole
configured week), or `instant` (the exact price at the evaluation moment).
`pricing.as_of` — or `--as-of` on `fetch`/`score`/`run` — evaluates schedules at
another timestamp (timestamps must carry a timezone). Providers that publish
per-model hours (OpenRouter's `pricing.overrides`) always use their own windows,
never `peak_windows_utc`; context-threshold prices still collapse via
`context_tier_policy`.

## Provider support

| Provider | chat | messages | responses | google |
|----------|:----:|:--------:|:---------:|:------:|
| CommandCode | yes | yes | — | — |
| OpenCode | yes | yes | translated | translated |
| OpenRouter | yes | — | — | — |

OpenCode's gateway serves every text model through every API: `responses`- and
`google`-native models are deployed through the `chat/completions` path, so they
are included instead of deferred. `messages`-native models keep the native
Anthropic path. The live `/models` response is the catalog; deprecated models
that remain in the docs table are not synthesized.

CommandCode's Provider API lists every model the gateway can serve, including
premium ones a lower subscription plan cannot use (e.g. GPT-6.1 Terra needs Pro).
The adapter reads the catalog page's own per-model minimum plan and drops
anything above `providers.commandcode.plan` (values `GO`, `GOAT`, `PRO`, `MAX`,
or `all` to disable the filter for pay-as-you-go keys). Unset = no filter. A
model with no plan data is dropped and reported rather than assumed available.

OpenRouter needs no scraping: its public models endpoint carries models **and**
prices. `:batch` variants are dropped inside the adapter (Batch API, not chat),
`:free` variants are kept as $0 deployments of their base model, and the
`openrouter/free` router entry is excluded through `exclude.patterns`.

All providers accept a key list. CommandCode and OpenCode use it for the
authenticated `/models` fetch; OpenRouter's catalog is public but the keys are
used when publishing. If one key fails authentication, payment, authorization,
rate limit, timeout/conflict, a 5xx, or the transport, the next key is tried; the
fetch phase fails only when every key fails. A `400`/`404` is treated as a
request/endpoint error, not a key error.

## Docs

- **[WALKTHROUGH.md](WALKTHROUGH.md)** — architecture, phases, data model, and
  the scoring/NMB algorithm in detail.
- Run `uv run --with pytest pytest tests/` for the unit tests.
