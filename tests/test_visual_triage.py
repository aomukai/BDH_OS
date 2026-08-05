import json

from training.pipeline.visual.triage import effective_triage, parse_triage_response


ASSET = "a" * 64


def test_parse_triage_response_accepts_fenced_json() -> None:
    rows = parse_triage_response(
        "```json\n" + json.dumps([{"asset_sha256": ASSET, "bucket": "accept", "reason": "clear"}]) + "\n```"
    )
    assert rows[0]["bucket"] == "accept"


def test_hard_gate_overrides_deepseek_accept() -> None:
    item = {"parse_ok": True, "hard_gate_reasons": ["text_or_watermark"]}
    result = effective_triage(item, {"bucket": "accept", "reason": "looks useful"})
    assert result["bucket"] == "reject"
    assert result["source"] == "deterministic_gate"


def test_parse_failure_is_check_again() -> None:
    result = effective_triage({"parse_ok": False}, {"bucket": "reject", "reason": "unknown"})
    assert result["bucket"] == "check_again"
