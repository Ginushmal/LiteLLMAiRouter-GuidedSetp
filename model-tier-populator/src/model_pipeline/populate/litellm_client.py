"""LiteLLM management API client.

Requires ``store_model_in_db: true`` (already enabled in this project).
Endpoints used:
  GET   /model/info             list models
  POST  /model/new              create
  PATCH /model/{model_id}/update  update (merges litellm_params and model_info)
  POST  /model/delete           delete (body {"id": ...})

The legacy ``POST /model/update`` is deliberately unused: it writes
``litellm_params`` but ignores ``model_info``, so token limits could never
converge through it (its own docstring points at the PATCH endpoint).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from model_pipeline.config import Config
from model_pipeline.http import HttpClient


class LiteLLMClient:
    def __init__(self, cfg: Config, http: HttpClient):
        self.cfg = cfg
        self.http = http
        self.base_url = cfg.litellm.base_url.rstrip("/")
        self.master_key = cfg.secret(cfg.litellm.master_key_env)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.master_key}",
            "Content-Type": "application/json",
        }

    def list_models(self) -> list[dict[str, Any]]:
        resp = self.http.get(f"{self.base_url}/model/info", headers=self._headers())
        resp.raise_for_status()
        return resp.json().get("data", [])

    def add_model(self, payload: dict[str, Any]) -> httpx.Response:
        return self.http.post_json(
            f"{self.base_url}/model/new", headers=self._headers(), payload=payload
        )

    def patch_model(self, model_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PATCH one stored model.

        The id is percent-encoded: it is a single path segment, so anything that
        would split the route (``/``) has to be escaped. The pipeline keeps its
        ids URL-safe (see ``models.safe_id_part``) but encoding costs nothing.
        """
        url = f"{self.base_url}/model/{quote(model_id, safe=':')}/update"
        return self.http.patch_json(url, headers=self._headers(), payload=payload)

    def delete_model(self, model_id: str) -> httpx.Response:
        return self.http.post_json(
            f"{self.base_url}/model/delete",
            headers=self._headers(),
            payload={"id": model_id},
        )
