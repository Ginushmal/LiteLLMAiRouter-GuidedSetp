"""Tests for the interactive populate preview and the plan/apply split."""

from types import SimpleNamespace

import pytest

from model_pipeline.cli import _cmd_populate_interactive, build_parser, cmd_populate
from model_pipeline.populate.litellm_client import LiteLLMClient
from model_pipeline.populate.sync import apply_plan, build_plan

BASE_URL = "https://elevate.ironone.com/"
DEPLOYMENT_ID = "mp::pro-tier::commandcode::x"


def _cfg(tmp_path, secret="sk-test"):
    def get_secret(name):
        if secret is None:
            raise RuntimeError(f"Missing secret '{name}'.")
        return secret

    return SimpleNamespace(
        output_dir=tmp_path,
        litellm=SimpleNamespace(
            base_url=BASE_URL,
            master_key_env="LITELLM_MASTER_KEY",
        ),
        secret=get_secret,
    )


def _payload():
    return {
        "tiers": [
            {
                "deployments": [
                    {
                        "model_group": "pro-tier",
                        "provider": "commandcode",
                        "model_id": "x",
                        "litellm_params": {
                            "model_name": "pro-tier",
                            "litellm_params": {"model": "openai/x", "order": 1},
                            "model_info": {},
                        },
                    }
                ]
            }
        ]
    }


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttp:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append(url)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, models, details=None, details_error=None, models_error=None):
        self.models = models
        self.details = details or {
            "base_url": BASE_URL,
            "status": "healthy",
            "db": "connected",
            "version": "1.103.0",
        }
        self.details_error = details_error
        self.models_error = models_error
        self.writes = []

    def server_details(self):
        if self.details_error:
            raise self.details_error
        return self.details

    def list_models(self):
        if self.models_error:
            raise self.models_error
        return self.models

    def add_model(self, payload):
        self.writes.append(("add", payload["model_info"]["id"]))
        return FakeResponse()

    def patch_model(self, model_id, payload):
        self.writes.append(("patch", model_id))
        return FakeResponse()

    def delete_model(self, model_id):
        self.writes.append(("delete", model_id))
        return FakeResponse()


# -- plan/apply parity ----------------------------------------------------
def test_plan_reports_the_sets_apply_uses_without_writing():
    client = FakeClient([])
    plan = build_plan(_payload(), client.models)

    assert plan.report.added == [DEPLOYMENT_ID]
    assert plan.report.updated == []
    assert plan.report.deleted == []
    assert client.writes == []

    applied = apply_plan(client, plan)
    assert applied.added == plan.report.added
    assert applied.updated == plan.report.updated
    assert applied.deleted == plan.report.deleted
    assert client.writes == [("add", DEPLOYMENT_ID)]


# -- server details -------------------------------------------------------
def test_server_details_reads_the_detailed_endpoint():
    http = FakeHttp(
        [
            FakeResponse(
                200,
                {"status": "healthy", "db": "connected", "litellm_version": "1.103.0"},
            )
        ]
    )
    cfg = SimpleNamespace(
        litellm=SimpleNamespace(base_url=BASE_URL, master_key_env="K"),
        secret=lambda name: "sk-test",
    )
    details = LiteLLMClient(cfg, http).server_details()

    assert details["version"] == "1.103.0"
    assert details["detailed"] is True
    assert http.calls == ["https://elevate.ironone.com/health/readiness/details"]


def test_server_details_falls_back_to_public_readiness():
    http = FakeHttp(
        [
            FakeResponse(404),
            FakeResponse(200, {"status": "healthy", "db": "connected"}),
        ]
    )
    cfg = SimpleNamespace(
        litellm=SimpleNamespace(base_url=BASE_URL, master_key_env="K"),
        secret=lambda name: "sk-test",
    )
    details = LiteLLMClient(cfg, http).server_details()

    assert details["version"] is None
    assert details["detailed"] is False
    assert http.calls == [
        "https://elevate.ironone.com/health/readiness/details",
        "https://elevate.ironone.com/health/readiness",
    ]


def test_server_details_raises_when_readiness_fails_too():
    http = FakeHttp([FakeResponse(401), FakeResponse(503)])
    cfg = SimpleNamespace(
        litellm=SimpleNamespace(base_url=BASE_URL, master_key_env="K"),
        secret=lambda name: "sk-test",
    )
    with pytest.raises(RuntimeError):
        LiteLLMClient(cfg, http).server_details()


# -- interactive preview --------------------------------------------------
def test_preview_shows_target_and_diff_without_writing(capsys, tmp_path):
    client = FakeClient([])
    rc = _cmd_populate_interactive(
        _cfg(tmp_path), _payload(), client, ask=lambda question: "n", isatty=True
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert BASE_URL in out
    assert "elevate.ironone.com" in out
    assert "LITELLM_MASTER_KEY" in out
    assert "sk-test" not in out
    assert "health: healthy (db: connected)" in out
    assert "version: 1.103.0" in out
    assert "pending changes: added=1" in out
    assert DEPLOYMENT_ID in out
    assert "populate declined" in out
    assert client.writes == []


@pytest.mark.parametrize("answer", ["", "n", "no", "N", "anything"])
def test_only_yes_applies(capsys, tmp_path, answer):
    client = FakeClient([])
    rc = _cmd_populate_interactive(
        _cfg(tmp_path), _payload(), client, ask=lambda question: answer, isatty=True
    )

    assert rc == 0
    assert client.writes == []
    assert "populate declined" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["y", "yes", "Y", "YES"])
def test_yes_applies_the_previewed_plan(capsys, tmp_path, answer):
    client = FakeClient([])
    rc = _cmd_populate_interactive(
        _cfg(tmp_path), _payload(), client, ask=lambda question: answer, isatty=True
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert client.writes == [("add", DEPLOYMENT_ID)]
    assert "populate applied: added=1" in out


def test_non_terminal_stdin_never_prompts_or_writes(capsys, tmp_path):
    client = FakeClient([])

    def must_not_ask(question):
        raise AssertionError("prompted without a terminal")

    rc = _cmd_populate_interactive(
        _cfg(tmp_path), _payload(), client, ask=must_not_ask, isatty=False
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "preview only" in out
    assert client.writes == []


def test_dry_run_previews_without_prompting_or_writing(capsys, tmp_path):
    client = FakeClient([])

    def must_not_ask(question):
        raise AssertionError("prompted during dry-run")

    rc = _cmd_populate_interactive(
        _cfg(tmp_path),
        _payload(),
        client,
        ask=must_not_ask,
        isatty=True,
        dry_run=True,
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run: no changes applied" in out
    assert client.writes == []


def test_unreachable_server_never_prompts_or_writes(capsys, tmp_path):
    client = FakeClient([], details_error=RuntimeError("connection refused"))

    def must_not_ask(question):
        raise AssertionError("prompted after a connection failure")

    rc = _cmd_populate_interactive(
        _cfg(tmp_path), _payload(), client, ask=must_not_ask, isatty=True
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert BASE_URL in captured.err
    assert "connection refused" in captured.err
    assert client.writes == []


def test_rejected_key_never_prompts_or_writes(capsys, tmp_path):
    client = FakeClient(
        [], models_error=RuntimeError("HTTP 401 Unauthorized")
    )

    def must_not_ask(question):
        raise AssertionError("prompted after an auth failure")

    rc = _cmd_populate_interactive(
        _cfg(tmp_path), _payload(), client, ask=must_not_ask, isatty=True
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "HTTP 401" in captured.err
    assert client.writes == []


# -- command plumbing -----------------------------------------------------
def test_parser_accepts_interactive():
    args = build_parser().parse_args(["populate", "--interactive"])
    assert args.interactive is True
    assert args.dry_run is False


def test_missing_tier_output_never_contacts_litellm(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("model_pipeline.cli.load_config", lambda config: _cfg(tmp_path))

    class MustNotConstruct:
        def __init__(self, *args, **kwargs):
            raise AssertionError("contacted LiteLLM without a tier list")

    monkeypatch.setattr("model_pipeline.cli.HttpClient", MustNotConstruct)
    args = SimpleNamespace(config=None, interactive=True, dry_run=False)

    rc = cmd_populate(args)

    assert rc == 2
    assert "tier-output.json" in capsys.readouterr().err


def test_missing_master_key_never_prompts(monkeypatch, capsys, tmp_path):
    (tmp_path / "tier-output.json").write_text("{}", encoding="utf-8")
    cfg = _cfg(tmp_path, secret=None)
    monkeypatch.setattr("model_pipeline.cli.load_config", lambda config: cfg)

    closed = []

    class FakeHttpClient:
        def close(self):
            closed.append(True)

    monkeypatch.setattr("model_pipeline.cli.HttpClient", FakeHttpClient)
    args = SimpleNamespace(config=None, interactive=True, dry_run=False)

    rc = cmd_populate(args)

    captured = capsys.readouterr()
    assert rc == 2
    assert BASE_URL in captured.err
    assert "Missing secret" in captured.err
    assert closed == [True]
