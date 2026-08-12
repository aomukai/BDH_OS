from image_benchmark.common import (
    REQUIRED_KEYS,
    admission_policy,
    parse_response,
    semantic_contract_errors,
)


def test_parse_response_preserves_schema_failures() -> None:
    parsed, errors = parse_response('{"admission":"usable"}')
    assert parsed == {"admission": "usable"}
    assert any(error.startswith("missing:") for error in errors)


def test_parse_response_accepts_contract() -> None:
    value = {
        "admission": "usable", "visible_text": False, "watermark": False,
        "quality_flags": [], "objects": [], "relationships": [],
        "literal_caption": "A dog.", "uncertainties": [],
    }
    import json
    parsed, errors = parse_response(json.dumps(value))
    assert set(parsed) == REQUIRED_KEYS
    assert errors == []


def test_watermark_must_not_be_admitted() -> None:
    assert semantic_contract_errors({
        "admission": "usable", "watermark": True, "quality_flags": []
    }) == ["policy:usable_watermark"]


def test_policy_overrides_model_admission_for_watermark() -> None:
    decision, reasons = admission_policy({
        "admission": "usable", "watermark": True, "quality_flags": [],
        "uncertainties": [],
    })
    assert decision == "unusable"
    assert reasons == ["watermark"]


def test_policy_routes_uncertainty_without_rejecting() -> None:
    decision, reasons = admission_policy({
        "admission": "usable", "watermark": False, "quality_flags": [],
        "uncertainties": ["small text is unclear"],
    })
    assert decision == "unresolved"
    assert reasons == ["uncertainty:small text is unclear"]


def test_policy_rejects_severe_quality_but_not_mild_quality() -> None:
    severe, _ = admission_policy({
        "admission": "usable", "watermark": False,
        "quality_flags": ["severe_compression"], "uncertainties": [],
    })
    mild, _ = admission_policy({
        "admission": "unusable", "watermark": False,
        "quality_flags": ["low_resolution"], "uncertainties": [],
    })
    assert severe == "unusable"
    assert mild == "usable"


def test_policy_never_accepts_incomplete_evidence() -> None:
    decision, reasons = admission_policy(
        {"admission": "usable", "watermark": False},
        ["missing:literal_caption"],
    )
    assert decision == "unresolved"
    assert reasons == ["schema:missing:literal_caption"]


def test_watermark_adjudication_can_clear_or_confirm_alarm() -> None:
    value = {
        "admission": "usable", "watermark": True, "quality_flags": [],
        "uncertainties": [],
    }
    assert admission_policy(value, watermark_adjudication="in_scene_text_or_branding") == (
        "usable", []
    )
    assert admission_policy(value, watermark_adjudication="uncertain") == (
        "unresolved", ["watermark_adjudication:uncertain"]
    )
