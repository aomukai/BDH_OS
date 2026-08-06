from mission_hub.handlers.cortex import _training_contract_mismatches


def test_training_contract_accepts_structured_effective_train_scope() -> None:
    expected = {"architecture": "cortex-v1", "train_scope": "full"}
    metadata = {
        "architecture": "cortex-v1",
        "train_scope": {"scope": "full", "trainable_parameters": 1_210_068_480},
    }

    assert _training_contract_mismatches(metadata, expected) == []


def test_training_contract_reports_precise_effective_scope_mismatch() -> None:
    expected = {"architecture": "cortex-v1", "train_scope": "full"}
    metadata = {
        "architecture": "cortex-v1",
        "train_scope": {"scope": "expression_bridge", "trainable_parameters": 10},
    }

    assert _training_contract_mismatches(metadata, expected) == [
        "train_scope: expected 'full', observed 'expression_bridge'"
    ]
