from __future__ import annotations

from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import ProtocolError
from mission_hub.jsonutil import content_hash
from mission_hub.protocol import validate_job_envelope


REPO = Path(__file__).resolve().parents[1]


def valid_envelope(bundle):
    body = {
        "schema_version": "ninereeds_job_envelope_v1",
        "protocol_version": 1,
        "job": {"id": "job-1", "type": "system.healthcheck", "version": 1, "input": {}, "input_sha256": content_hash({})},
        "run": {"id": "run-1", "attempt": 1},
        "lease": {"token": "secret", "expires_at": "2099-01-01T00:00:00Z"},
        "deployment": {"id": "dep-1", "machine_id": "trainbox", "role": "trainbox", "release_id": "release", "source_sha256": "a" * 64, "environment_sha256": "b" * 64},
        "config_snapshot": {"id": "cfg", "sha256": bundle.sha256},
        "artifacts": [],
        "issued_at": "2026-08-05T00:00:00Z",
    }
    body["envelope_hash"] = content_hash(body)
    return body


def test_envelope_tampering_is_rejected() -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    envelope = valid_envelope(bundle)
    envelope["job"]["input"] = {"include_gpu": False}
    with pytest.raises(ProtocolError, match="hash mismatch"):
        validate_job_envelope(
            bundle,
            envelope,
            machine_id="trainbox",
            deployment={"id": "dep-1", "release_id": "release", "source_sha256": "a" * 64, "environment_sha256": "b" * 64},
        )
