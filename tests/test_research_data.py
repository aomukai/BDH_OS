from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from campaign36c.research_data import (
    DATASET_SCHEMA,
    iter_dataset_records,
    validate_dataset_manifest,
)
from mission_hub.errors import SafetyError
from mission_hub.handlers.research_data import _public_https_url
from meta.scripts.train_campaign36c_research import (
    _epoch_records,
    _spool_records,
)


def manifest(path: Path) -> dict:
    raw = path.read_bytes()
    return {
        "schema_version": DATASET_SCHEMA,
        "dataset_name": "bounded-text-v1",
        "source": {
            "url": "https://example.org/bounded.jsonl",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_size": len(raw),
        },
        "adapter": {
            "format": "jsonl",
            "archive": "none",
            "records_member": None,
            "modality": "text",
            "objective": "continuation",
            "text_field": "text",
            "prompt_field": None,
            "completion_field": None,
            "image_field": None,
            "caption_field": None,
        },
    }


def test_text_dataset_is_content_bound_and_spooled_with_stable_lineages(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "records.jsonl"
    dataset.write_text(
        "\n".join(json.dumps({"text": f"Article {index} has enough words to split."}) for index in range(5)) + "\n",
        encoding="utf-8",
    )
    specification = manifest(dataset)

    records = list(iter_dataset_records(dataset, specification))
    assert len(records) == 5
    assert len({item["evidence_lineage"] for item in records}) == 5
    assert {item["modality"] for item in records} == {"text"}

    spool = tmp_path / "records.sqlite3"
    assert _spool_records(spool, dataset, specification, limit=4) == 4
    declared = [item["record_id"] for item in _epoch_records(
        spool, order_policy="declared", order_seed=36, epoch=0,
    )]
    shuffled_a = [item["record_id"] for item in _epoch_records(
        spool, order_policy="reshuffle_each_epoch", order_seed=36, epoch=0,
    )]
    shuffled_b = [item["record_id"] for item in _epoch_records(
        spool, order_policy="reshuffle_each_epoch", order_seed=36, epoch=1,
    )]
    assert sorted(declared) == sorted(shuffled_a) == sorted(shuffled_b)
    assert shuffled_a != shuffled_b


def test_image_text_adapter_requires_one_safe_archive_member(tmp_path: Path) -> None:
    dataset = tmp_path / "bundle.zip"
    dataset.write_bytes(b"not used")
    value = manifest(dataset)
    value["adapter"].update({
        "archive": "zip",
        "modality": "image_text",
        "records_member": "../records.jsonl",
        "text_field": None,
        "image_field": "image",
        "caption_field": "caption",
    })
    with pytest.raises(ValueError, match="unsafe"):
        validate_dataset_manifest(value)


def test_dataset_acquisition_refuses_private_network_targets() -> None:
    with pytest.raises(SafetyError, match="outside the public internet"):
        _public_https_url("https://127.0.0.1/dataset.jsonl")
