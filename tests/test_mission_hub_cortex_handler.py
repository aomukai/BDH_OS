from mission_hub.handlers.cortex import _training_contract_mismatches
from mission_hub.handlers.visual import _local_runtime_failure


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


def test_pytorch_checkpoint_stream_failure_is_classified_as_disk_write_failure() -> None:
    stderr = """
RuntimeError: basic_ios::clear: iostream error
RuntimeError: [enforce fail at inline_container.cc:668] . unexpected pos 4168792448 vs 4168792336
"""

    assert _local_runtime_failure(1, stderr) == (
        "operational_transient", "disk_write_failed",
    )
