"""Audited acquisition of one public dataset for the Mycelium research lab."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import tempfile
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from campaign36c.research_data import DATASET_SCHEMA, inspect_dataset, validate_dataset_manifest

from ..artifacts import sha256_file
from ..errors import RemoteJobError, SafetyError
from ..jsonutil import content_hash


def _public_https_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SafetyError("research datasets require a credential-free public HTTPS URL")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RemoteJobError(
            f"dataset host could not be resolved: {parsed.hostname}",
            failure_class="operational_transient",
            code="resource_temporarily_unavailable",
        ) from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if not address.is_global:
            raise SafetyError("research dataset URL resolved outside the public internet")
    return urllib.parse.urlunsplit(parsed)


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return super().redirect_request(req, fp, code, msg, headers, _public_https_url(newurl))


def _artifact(kind: str, path: Path, manifest: dict[str, Any], *, lifecycle: str = "candidate") -> dict[str, Any]:
    return {
        "kind": kind,
        "sha256": sha256_file(path),
        "byte_size": path.stat().st_size,
        "uri": str(path),
        "lifecycle": lifecycle,
        "manifest": manifest,
    }


class ResearchDatasetAcquireHandler:
    """Download, hash, inspect, and register one immutable public dataset file."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        source_url = _public_https_url(payload["source_url"])
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        temporary_root = Path(context["state_root"]).resolve() / "dataset-downloads"
        temporary_root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(temporary_root).free < min(
            payload["max_download_bytes"] + 4 * 1024**3,
            8 * 1024**3,
        ):
            raise SafetyError("Trainbox has insufficient free space for dataset acquisition")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".research-dataset-", dir=temporary_root)
        temporary = Path(temporary_name)
        digest = hashlib.sha256()
        received = 0
        final_url = source_url
        content_type = None
        try:
            request = urllib.request.Request(
                source_url,
                headers={"User-Agent": "Ninereeds-Research-Lab/1.0"},
                method="GET",
            )
            opener = urllib.request.build_opener(
                _PublicRedirects(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
            )
            try:
                response = opener.open(request, timeout=min(context["timeout_seconds"], 300))
            except (OSError, urllib.error.URLError) as exc:
                raise RemoteJobError(
                    f"public dataset download failed: {exc}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                ) from exc
            with os.fdopen(descriptor, "wb") as output, response:
                final_url = _public_https_url(response.geturl())
                content_type = response.headers.get("Content-Type")
                declared = response.headers.get("Content-Length")
                if declared:
                    try:
                        declared_size = int(declared)
                    except ValueError as exc:
                        raise SafetyError("public dataset returned an invalid Content-Length") from exc
                    if declared_size > payload["max_download_bytes"]:
                        raise SafetyError("public dataset exceeds its authorized download bound")
                while chunk := response.read(8 * 1024 * 1024):
                    received += len(chunk)
                    if received > payload["max_download_bytes"]:
                        raise SafetyError("public dataset exceeded its authorized download bound")
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            if received == 0:
                raise SafetyError("public dataset download was empty")
            observed_sha = digest.hexdigest()
            expected_sha = payload.get("expected_sha256")
            if expected_sha is not None and observed_sha != expected_sha:
                raise SafetyError("public dataset bytes do not match the expected SHA-256")
            free = shutil.disk_usage(temporary_root).free
            if free < max(4 * 1024**3, received):
                raise SafetyError("dataset acquisition would leave insufficient Trainbox free space")
            object_path = (
                Path(context["state_root"]).resolve()
                / "artifacts" / "objects" / observed_sha[:2] / observed_sha
            )
            object_path.parent.mkdir(parents=True, exist_ok=True)
            if object_path.exists():
                if object_path.stat().st_size != received or sha256_file(object_path) != observed_sha:
                    raise SafetyError("existing dataset object conflicts with its content hash")
                temporary.unlink()
            else:
                os.chmod(temporary, 0o440)
                os.replace(temporary, object_path)
            manifest = validate_dataset_manifest({
                "schema_version": DATASET_SCHEMA,
                "dataset_name": payload["dataset_name"],
                "source": {
                    "url": source_url,
                    "final_url": final_url,
                    "source_page_url": payload.get("source_page_url"),
                    "license": payload.get("license"),
                    "sha256": observed_sha,
                    "byte_size": received,
                    "content_type": content_type,
                    "public_download": True,
                },
                "adapter": {
                    "format": payload["dataset_format"],
                    "archive": payload["archive_format"],
                    "records_member": payload.get("records_member"),
                    "modality": payload["modality"],
                    "objective": payload["objective"],
                    "text_field": payload.get("text_field"),
                    "prompt_field": payload.get("prompt_field"),
                    "completion_field": payload.get("completion_field"),
                    "image_field": payload.get("image_field"),
                    "caption_field": payload.get("caption_field"),
                },
            })
            inspection = inspect_dataset(object_path, manifest)
            artifact_id = f"art-{content_hash({'kind': 'research_dataset', 'sha256': observed_sha})[:16]}"
            log_path = run_root / "research-dataset-acquisition.json"
            log_path.write_text(json.dumps({
                "schema_version": "ninereeds_research_dataset_acquisition_v1",
                "dataset_artifact_id": artifact_id,
                "manifest": manifest,
                "inspection": inspection,
            }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return {
                "status": "succeeded",
                "artifacts": [
                    _artifact("research_dataset", object_path, manifest),
                    _artifact("log", log_path, {
                        "schema_version": "ninereeds_research_dataset_acquisition_v1",
                        "dataset_artifact_id": artifact_id,
                    }, lifecycle="observed"),
                ],
                "metrics": {
                    "dataset_artifact_id": artifact_id,
                    "dataset_name": payload["dataset_name"],
                    "sha256": observed_sha,
                    "byte_size": received,
                    "modality": payload["modality"],
                    "format": payload["dataset_format"],
                    "inspection": inspection,
                },
                "failure": None,
            }
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
