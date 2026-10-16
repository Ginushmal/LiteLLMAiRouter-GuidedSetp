"""Multi-provider LLM model pipeline.

Three independently invocable phases:
  fetch   -> provider adapters + canonical dedup -> mappings.csv
  score   -> mappings + AA data + config -> tier-output.json / .md
  populate-> tier-output.json -> LiteLLM management API
"""

__version__ = "0.1.0"
