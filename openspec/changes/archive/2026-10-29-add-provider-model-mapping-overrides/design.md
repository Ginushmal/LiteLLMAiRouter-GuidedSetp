# Technical Design: Provider Model Mapping Overrides

## Context

In `model-pipeline`, the deduplication phase (`map_models` in `src/model_pipeline/dedup/mapper.py`) matches provider `RawModel` instances to `CanonicalModel` instances scraped from Artificial Analysis. Currently, matching runs in two steps:
1. Exact match on normalized strings (`index.exact()`).
2. Jev classifier over a candidate shortlist.

When a provider uses an identical or ambiguous name for a different model version (e.g., CommandCode naming its `deepseek-v4-1-flash-1017` deployment as `deepseek/deepseek-v4.1-flash`), the exact match step matches the older `deepseek-v4-1-flash` slug. Overriding this currently requires post-hoc manual editing of `output/mappings.csv`, which is lost every time `fetch` or `refresh` runs.

See `proposal.md` for background and motivation.

## Goals / Non-Goals

**Goals:**
- Provide a clean, declarative configuration in `config.yaml` under each provider definition (`providers.<name>.model_mappings`) to map provider model IDs to canonical Artificial Analysis slugs.
- Execute configured overrides before exact matching and Jev classification in `map_models()`.
- Populate `Mapping` records with `method="override"`, `confidence=1.0`, and the resolved canonical slug and name.
- Preserve full transparency in `output/mappings.csv` and seamless compatibility with `score` and `refresh`.
- Validate target canonical slugs against the Artificial Analysis catalog, warning on invalid slugs.

**Non-Goals:**
- Altering the Jev classifier prompt or candidate shortlisting logic for unconfigured models.
- Changing token-limit resolution (`limits.py`) or scoring logic (`scoring/pipeline.py`).
- Global cross-provider mapping rules (overrides remain scoped to the specific provider).

## Decisions

### Decision 1: Configuration Schema under `ProviderConfig`
Place `model_mappings: dict[str, str]` inside each provider block under `providers.<provider>`:

```yaml
providers:
  commandcode:
    enabled: true
    # ...
    model_mappings:
      "deepseek/deepseek-v4.1-flash": "deepseek-v4-1-flash-1017"
      "deepseek/deepseek-v4.1-flash-fast": "deepseek-v4-1-flash-1017"
```

*Rationale*: Model naming discrepancies are specific to individual providers. Placing the dictionary under the provider keeps connection details, endpoint URLs, and model-specific corrections encapsulated together.

*Alternatives Considered*:
- Top-level `mappings.overrides`: Separates mapping from provider configuration, requiring compound keys or redundant provider nesting.
- `dedup.overrides`: Conflates provider-specific quirks with generic string normalization rules.

### Decision 2: Override Evaluation Order in `map_models`
In `src/model_pipeline/dedup/mapper.py`, check `cfg.providers[m.provider].model_mappings` at Step 0, before `index.exact()`:

```
[ Provider RawModel ]
        |
        v
+-----------------------------------+
| Step 0: Check model_mappings?     | -- YES --> [ Resolved via Override ]
+-----------------------------------+            (method="override", conf=1.0)
        | NO
        v
+-----------------------------------+
| Step 1: CanonicalIndex.exact()?   | -- YES --> [ Exact Match ]
+-----------------------------------+            (method="exact", conf=1.0)
        | NO
        v
+-----------------------------------+
| Step 2: Jev Classifier Shortlist  | ---------> [ Jev Match / Unmapped ]
+-----------------------------------+
```

*Rationale*: A user-configured override is an explicit human truth assertion. It must supersede heuristic string normalization and LLM-based classification.

### Decision 3: Handling Missing or Unknown Target Slugs
When an override specifies a slug not found in the loaded `canonical_models`:
- Print a warning to `sys.stderr` indicating `model_mappings: target slug '<slug>' for '<provider>:<model_id>' does not exist in canonical models`.
- Record the `Mapping` with `canonical_slug=None`, `canonical_name=None`, `method="unmapped"`, `confidence=0.0`, and record the error in `probabilities`.

*Rationale*: Prevents pipeline crashes if a typo occurs in `config.yaml`, while strictly refusing to invent fictitious models with missing pricing and benchmark data.

### Decision 4: Artifact Representation
`Mapping` instances created via overrides will set:
- `canonical_slug`: target slug
- `canonical_name`: target canonical model's display name from catalog
- `method`: `"override"`
- `confidence`: `1.0`
- `override`: target slug
- `low_confidence`: `False`

*Rationale*: `mappings.csv` will show `method=override` and `confidence=1.0000`, clearly distinguishing configuration overrides from automated exact matches and low-confidence Jev guesses. Downstream `score` will consume `effective_slug` smoothly.

## Risks / Trade-offs

- **[Risk] Typo in canonical slug in `config.yaml`**
  $\rightarrow$ *Mitigation*: Validated during `map_models()` against loaded AA catalog; emits clear warning and leaves model unmapped.
- **[Risk] Model ID changes in upstream provider API**
  $\rightarrow$ *Mitigation*: Unmatched overrides simply do not trigger; new model IDs follow normal exact/Jev matching.
- **[Risk] Multiple casing or formatting variations in model ID**
  $\rightarrow$ *Mitigation*: Compare against exact raw `model_id` first, falling back to trimmed/normalized `model_id`.

## Migration Plan

1. Update `ProviderConfig` dataclass and `load_config` in `src/model_pipeline/config.py` with `model_mappings: dict[str, str] = field(default_factory=dict)`.
2. Update `src/model_pipeline/dedup/mapper.py` to evaluate `cfg.providers[m.provider].model_mappings`.
3. Add unit tests verifying override behavior, slug validation, and precedence over exact matching.
4. Update `config.example.yaml` with documentation and an example in the `commandcode` provider block.
