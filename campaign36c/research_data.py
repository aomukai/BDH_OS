"""Immutable research-dataset adapters for the Mycelium laboratory.

This module is deliberately independent from the V8 curriculum contract.  It reads
one content-hashed public research artifact according to the adapter recorded in the
artifact manifest.  Ordering and epoch policy remain experiment inputs, never mutable
properties of the downloaded bytes.
"""

from __future__ import annotations

from contextlib import contextmanager
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any, BinaryIO, Iterator
import zipfile


DATASET_SCHEMA = "ninereeds_mycelium_research_dataset_v1"
FORMATS = {"text", "jsonl", "json", "csv", "parquet"}
ARCHIVES = {"none", "gzip", "zip", "tar"}
MODALITIES = {"text", "image_text"}
OBJECTIVES = {"continuation", "reconstruction", "prompt_completion"}


def clean_member(value: str) -> str:
    """Return one safe POSIX archive member name."""
    member = PurePosixPath(value)
    if (
        not value
        or member.is_absolute()
        or ".." in member.parts
        or "\\" in value
        or value.endswith("/")
    ):
        raise ValueError(f"dataset archive member is unsafe: {value!r}")
    return member.as_posix()


def validate_dataset_manifest(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") != DATASET_SCHEMA:
        raise ValueError("research dataset has an unsupported manifest schema")
    adapter = value.get("adapter")
    if not isinstance(adapter, dict):
        raise ValueError("research dataset manifest has no adapter")
    if adapter.get("format") not in FORMATS:
        raise ValueError("research dataset has an unsupported record format")
    if adapter.get("archive") not in ARCHIVES:
        raise ValueError("research dataset has an unsupported archive format")
    if adapter.get("modality") not in MODALITIES:
        raise ValueError("research dataset has an unsupported modality")
    if adapter.get("objective") not in OBJECTIVES:
        raise ValueError("research dataset has an unsupported objective")
    member = adapter.get("records_member")
    if adapter["archive"] in {"zip", "tar"}:
        if not isinstance(member, str):
            raise ValueError("zip and tar datasets require one records_member")
        clean_member(member)
    elif member is not None:
        raise ValueError("unarchived and gzip datasets cannot declare records_member")
    if adapter["format"] == "parquet" and adapter["archive"] != "none":
        raise ValueError("parquet research datasets must be downloaded as a direct file")

    modality = adapter["modality"]
    objective = adapter["objective"]
    if modality == "text":
        if objective == "prompt_completion":
            if not adapter.get("prompt_field") or not adapter.get("completion_field"):
                raise ValueError("prompt_completion datasets require both field names")
        elif adapter["format"] != "text" and not adapter.get("text_field"):
            raise ValueError("structured continuation/reconstruction datasets require text_field")
        if adapter.get("image_field") is not None or adapter.get("caption_field") is not None:
            raise ValueError("text datasets cannot declare image fields")
    else:
        if not adapter.get("image_field") or not adapter.get("caption_field"):
            raise ValueError("image_text datasets require image_field and caption_field")
        if adapter["archive"] not in {"zip", "tar"}:
            raise ValueError("image_text datasets must use one zip or tar artifact")
    return value


@contextmanager
def _record_stream(path: Path, adapter: dict[str, Any]) -> Iterator[BinaryIO]:
    archive = adapter["archive"]
    if archive == "none":
        with path.open("rb") as handle:
            yield handle
        return
    if archive == "gzip":
        with gzip.open(path, "rb") as handle:
            yield handle
        return
    member = clean_member(adapter["records_member"])
    if archive == "zip":
        with zipfile.ZipFile(path) as bundle:
            names = {clean_member(item.filename) for item in bundle.infolist() if not item.is_dir()}
            if member not in names:
                raise ValueError(f"research dataset archive lacks records member {member}")
            with bundle.open(member, "r") as handle:
                yield handle
        return
    with tarfile.open(path, "r:*") as bundle:
        entries = {
            clean_member(item.name): item
            for item in bundle.getmembers()
            if item.isfile() and not item.issym() and not item.islnk()
        }
        item = entries.get(member)
        if item is None:
            raise ValueError(f"research dataset archive lacks records member {member}")
        handle = bundle.extractfile(item)
        if handle is None:
            raise ValueError(f"research dataset cannot read records member {member}")
        with handle:
            yield handle


def _raw_records(path: Path, adapter: dict[str, Any]) -> Iterator[dict[str, Any] | str]:
    record_format = adapter["format"]
    if record_format == "parquet":
        import pyarrow.parquet as parquet

        source = parquet.ParquetFile(path)
        for batch in source.iter_batches(batch_size=1024):
            yield from batch.to_pylist()
        return
    with _record_stream(path, adapter) as binary:
        text = io.TextIOWrapper(binary, encoding="utf-8", errors="strict", newline="")
        if record_format == "text":
            paragraph: list[str] = []
            for line in text:
                stripped = line.strip()
                if stripped:
                    paragraph.append(stripped)
                elif paragraph:
                    yield " ".join(paragraph)
                    paragraph = []
            if paragraph:
                yield " ".join(paragraph)
            return
        if record_format == "jsonl":
            for line_number, line in enumerate(text, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"JSONL record {line_number} is not an object")
                yield value
            return
        if record_format == "csv":
            yield from csv.DictReader(text)
            return
        value = json.load(text)
        if isinstance(value, list):
            records = value
        elif isinstance(value, dict) and isinstance(value.get("records"), list):
            records = value["records"]
        else:
            raise ValueError("JSON research dataset must be an array or contain a records array")
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                raise ValueError(f"JSON dataset record {index} is not an object")
            yield item


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"research dataset field {field!r} must contain non-empty text")
    return " ".join(value.split())


def _continuation(value: str) -> tuple[str, str]:
    normalized = " ".join(value.split())
    if len(normalized) < 2:
        raise ValueError("continuation record is too short")
    target = max(1, min(len(normalized) - 1, int(len(normalized) * 0.75)))
    left = normalized.rfind(" ", 1, target + 1)
    split = left if left > 0 else target
    prompt = normalized[max(0, split - 2048) : split].strip()
    completion = normalized[split : split + 512].strip()
    if not prompt or not completion:
        midpoint = max(1, len(normalized) // 2)
        prompt = normalized[max(0, midpoint - 2048) : midpoint].strip()
        completion = normalized[midpoint : midpoint + 512].strip()
    if not prompt or not completion:
        raise ValueError("continuation record cannot be split into prompt and completion")
    return prompt, completion


def iter_dataset_records(path: Path, manifest: dict[str, Any]) -> Iterator[dict[str, Any]]:
    manifest = validate_dataset_manifest(manifest)
    adapter = manifest["adapter"]
    dataset_sha = manifest["source"]["sha256"]
    records_member = adapter.get("records_member")
    record_parent = PurePosixPath(records_member).parent if records_member else PurePosixPath(".")
    for ordinal, raw in enumerate(_raw_records(path, adapter)):
        try:
            if adapter["modality"] == "image_text":
                assert isinstance(raw, dict)
                image_value = _text(raw.get(adapter["image_field"]), field=adapter["image_field"])
                image_member = clean_member((record_parent / image_value).as_posix())
                caption = _text(raw.get(adapter["caption_field"]), field=adapter["caption_field"])
                prompt, completion = caption, caption
            elif adapter["objective"] == "prompt_completion":
                assert isinstance(raw, dict)
                prompt = _text(raw.get(adapter["prompt_field"]), field=adapter["prompt_field"])
                completion = _text(
                    raw.get(adapter["completion_field"]), field=adapter["completion_field"]
                )[:512]
                image_member = None
            else:
                if isinstance(raw, str):
                    value = _text(raw, field="text")
                else:
                    value = _text(raw.get(adapter["text_field"]), field=adapter["text_field"])
                if adapter["objective"] == "continuation":
                    prompt, completion = _continuation(value)
                else:
                    prompt, completion = value[-2048:], value[:512]
                image_member = None
        except ValueError:
            # Public corpora commonly contain blank or malformed rows.  Skipping is
            # deterministic and the final counters make the disposition observable.
            continue
        record_id = hashlib.sha256(
            f"{dataset_sha}:{ordinal}".encode("utf-8")
        ).hexdigest()
        yield {
            "record_id": record_id,
            "ordinal": ordinal,
            "modality": adapter["modality"],
            "prompt": prompt,
            "completion": completion,
            "image_member": image_member,
            "source_family": f"dataset:{dataset_sha[:16]}",
            "evidence_lineage": f"dataset:{dataset_sha}:{ordinal}",
        }


def load_record_image(path: Path, manifest: dict[str, Any], member_name: str) -> Any:
    """Load one verified archive member as an RGB Pillow image."""
    from PIL import Image

    adapter = validate_dataset_manifest(manifest)["adapter"]
    member = clean_member(member_name)
    if adapter["archive"] == "zip":
        with zipfile.ZipFile(path) as bundle:
            info = bundle.getinfo(member)
            if info.is_dir():
                raise ValueError(f"image member is a directory: {member}")
            payload = bundle.read(info)
    elif adapter["archive"] == "tar":
        with tarfile.open(path, "r:*") as bundle:
            info = bundle.getmember(member)
            if not info.isfile() or info.issym() or info.islnk():
                raise ValueError(f"image member is not a regular file: {member}")
            handle = bundle.extractfile(info)
            if handle is None:
                raise ValueError(f"image member is unreadable: {member}")
            payload = handle.read()
    else:
        raise ValueError("image_text dataset is not an archive")
    with Image.open(io.BytesIO(payload)) as image:
        image.load()
        return image.convert("RGB")


def inspect_dataset(path: Path, manifest: dict[str, Any], *, sample_limit: int = 8) -> dict[str, Any]:
    manifest = validate_dataset_manifest(manifest)
    samples = []
    for record in iter_dataset_records(path, manifest):
        samples.append({
            "record_id": record["record_id"],
            "modality": record["modality"],
            "prompt_characters": len(record["prompt"]),
            "completion_characters": len(record["completion"]),
            "has_image": record["image_member"] is not None,
        })
        if len(samples) >= sample_limit:
            break
    if not samples:
        raise ValueError("research dataset contains no usable records")
    record_count = None
    if manifest["adapter"]["format"] == "parquet":
        import pyarrow.parquet as parquet

        record_count = parquet.ParquetFile(path).metadata.num_rows
    return {"sampled_records": len(samples), "declared_record_count": record_count, "samples": samples}
