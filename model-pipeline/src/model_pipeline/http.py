"""HTTP client + scraping forensics.

Every fetch is recorded twice:
  * the verbatim body is saved under ``data/raw/<provider>/`` so a human or an
    AI agent can inspect exactly what the site returned, and
  * a structured JSON-lines entry is appended to ``data/logs/<provider>/`` with
    the URL, timestamp, status, parse counts, and any error.

That makes a future scraping break ("the page changed and parsing now returns
0 rows") diagnosable from the artifacts alone.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

USER_AGENT = "model-pipeline/0.1 (+https://github.com/)"


@dataclass
class ScrapeRecord:
    provider: str
    url: str
    method: str
    status: Optional[int]
    timestamp: str
    content_type: str = ""
    body_bytes: int = 0
    raw_path: str = ""
    parsed_count: Optional[int] = None
    error: str = ""
    notes: str = ""


def _slugify(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:60] or "root"


class ScrapeRecorder:
    """Saves raw scrape artifacts and structured logs."""

    def __init__(self, raw_dir: Path, logs_dir: Path):
        self.raw_dir = raw_dir
        self.logs_dir = logs_dir

    def record(self, rec: ScrapeRecord, body: str = "") -> ScrapeRecord:
        provider_dir = self.raw_dir / rec.provider
        log_dir = self.logs_dir / rec.provider
        provider_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        if body:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            ext = "json" if "json" in rec.content_type else "html"
            raw_path = provider_dir / f"{stamp}_{_slugify(rec.url)}.{ext}"
            raw_path.write_text(body, encoding="utf-8", errors="replace")
            rec.raw_path = str(raw_path)
            rec.body_bytes = len(body.encode("utf-8", errors="replace"))

        log_file = log_dir / f"{datetime.now(timezone.utc):%Y-%m-%d}.log"
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
        return rec


class HttpClient:
    """Thin httpx wrapper that always sends a real User-Agent."""

    def __init__(self, timeout: float = 30.0, user_agent: str = USER_AGENT):
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "*/*"},
            timeout=timeout,
            follow_redirects=True,
        )

    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        return self._client.get(url, headers=headers)

    def post_json(
        self, url: str, headers: dict[str, str] | None = None, payload: Any = None
    ) -> httpx.Response:
        return self._client.post(url, headers=headers, json=payload)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
