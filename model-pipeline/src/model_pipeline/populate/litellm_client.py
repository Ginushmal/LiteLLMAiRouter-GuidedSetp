"""LiteLLM management API client.

Requires ``store_model_in_db: true`` (already enabled in this project).
Endpoints used:
  GET  /model/info      list models
  POST /model/new       create
  POST /model/update    update
  POST /model/delete    delete (body {"id": ...})
"""

from __future__ import annotations

from typing import Any

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

    def update_model(self, payload: dict[str, Any]) -> httpx.Response:
        return self.http.post_json(
            f"{self.base_url}/model/update", headers=self._headers(), payload=payload
        )

    def delete_model(self, model_id: str) -> httpx.Response:
        return self.http.post_json(
            f"{self.base_url}/model/delete",
            headers=self._headers(),
            payload={"id": model_id},
        )
