"""Regression checks that raw API keys never enter artifacts or logs."""

import json
from types import SimpleNamespace

from model_pipeline.models import (
    Credential,
    Deployment,
    ResolvedPricing,
)
from model_pipeline.populate.credentials import resolve_payload_credentials
from model_pipeline.providers.base import ProviderAdapter

SECRET = "sk-LEAK-ME-123456"


class _Adapter(ProviderAdapter):
    name = "ours"

    def __init__(self):
        self.pcfg = SimpleNamespace(api_key_env="", api_keys_env="OURS_APIS", extra_headers={})
        self.cfg = SimpleNamespace(
            litellm=SimpleNamespace(num_retries=32, allowed_fails=0, cooldown_time=1800)
        )

    def fetch_models(self):  # pragma: no cover
        return []

    def fetch_pricing(self):  # pragma: no cover
        return {}

    def to_litellm_deployment(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


def test_assembled_payload_and_deployment_artifact_never_contain_the_key():
    adapter = _Adapter()
    credential = Credential(2, SECRET, "OURS_APIS", raw=True)
    model = adapter._assemble(
        # minimal RawModel-like object
        SimpleNamespace(
            model_id="gpt-x",
            display_name="GPT X",
            input_tokens=1000,
            output_tokens=100,
            capabilities={"supports_vision": True},
        ),
        ResolvedPricing(input=1.0, output=2.0),
        "pro-tier",
        2,
        "openai/gpt-x",
        "https://api.example/v1",
        credential,
    )

    assert SECRET not in json.dumps(model)

    deployment = Deployment(
        canonical_slug="a",
        canonical_name="A",
        provider="ours",
        model_id="gpt-x",
        display_name="GPT X",
        endpoint_type="chat",
        api_base="https://api.example/v1",
        api_key_env="OURS_APIS",
        intelligence=50,
        cost_per_task=1.0,
        model_group="pro-tier",
        order=2,
        credential_slot=2,
        api_key_fingerprint=credential.fingerprint,
        litellm_params=model,
    )
    assert SECRET not in json.dumps(deployment.to_dict())


def test_populate_resolution_adds_the_key_only_after_the_artifact_is_read():
    payload = {
        "tiers": [
            {
                "deployments": [
                    {
                        "provider": "ours",
                        "credential_slot": 2,
                        "litellm_params": {"model": "openai/gpt-x", "order": 2},
                        "model_info": {"id": "mp::key-2"},
                    }
                ]
            }
        ]
    }
    assert SECRET not in json.dumps(payload)

    cfg = SimpleNamespace(
        provider_credentials=lambda provider: [
            Credential(1, "first-key", "OURS_APIS", raw=True),
            Credential(2, SECRET, "OURS_APIS", raw=True),
        ]
    )
    resolve_payload_credentials(payload, cfg)
    assert payload["tiers"][0]["deployments"][0]["litellm_params"]["api_key"] == SECRET
