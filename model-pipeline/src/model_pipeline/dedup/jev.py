"""Jev (TypeSafe System One) classifier client.

Reached through the CommandCode Provider API's `v1/systemone` endpoint, so no
separate TypeSafe key is needed. We send the provider model name as `state`
and the shortlisted canonical names as a single-choice `criteria` question,
including an "unmapped" option so Jev can reject names it does not recognise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from model_pipeline.config import Config
from model_pipeline.http import HttpClient


@dataclass
class JevAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)


class JevClient:
    def __init__(self, cfg: Config, http: HttpClient):
        self.cfg = cfg
        self.http = http
        self.endpoint = cfg.jev.endpoint
        self.model = cfg.jev.model
        self.timeout = cfg.jev.timeout_seconds
        self.api_key = cfg.secret(cfg.jev.api_key_env)

    def choose(self, state: str, instructions: str, criteria: dict[str, str]) -> JevAnswer:
        payload: dict[str, Any] = {
            "model": self.model,
            "state": state,
            "questions": {
                "match": {
                    "type": "choice",
                    "instructions": instructions,
                    "criteria": criteria,
                }
            },
        }
        resp = self.http.post_json(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        resp.raise_for_status()
        answer = resp.json()["answers"]["match"]
        return JevAnswer(
            choice=answer["choice"],
            confidence=float(answer.get("confidence", 0.0)),
            probabilities=answer.get("probabilities", {}) or {},
        )
