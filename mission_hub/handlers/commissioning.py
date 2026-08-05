"""Deterministic handlers used only to commission artifact and GPU paths."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from ..artifacts import sha256_file
from ..errors import ProtocolError, SafetyError
from .healthcheck import HealthcheckHandler


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_root(context: dict[str, Any]) -> Path:
    root = Path(context["state_root"]) / "runs" / context["run"]["id"]
    root.mkdir(parents=True, exist_ok=False)
    return root


def _input_artifact(context: dict[str, Any], artifact_id: str, expected_kind: str) -> tuple[dict[str, Any], Path]:
    matches = [artifact for artifact in context["artifacts"] if artifact["id"] == artifact_id]
    if len(matches) != 1:
        raise ProtocolError(f"job did not receive exactly one artifact reference: {artifact_id}")
    artifact = matches[0]
    if artifact["kind"] != expected_kind:
        raise SafetyError(f"artifact {artifact_id} has kind {artifact['kind']}, expected {expected_kind}")
    path = Path(artifact["uri"]).resolve()
    roots = [Path(context["state_root"]).resolve(), *(Path(value).resolve() for value in context["artifact_roots"])]
    if not any(path == root or root in path.parents for root in roots):
        raise SafetyError(f"artifact path is outside configured roots: {artifact_id}")
    if not path.is_file() or path.stat().st_size != artifact["byte_size"] or sha256_file(path) != artifact["sha256"]:
        raise SafetyError(f"artifact bytes do not match the envelope: {artifact_id}")
    return artifact, path


def _declaration(kind: str, path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "sha256": sha256_file(path),
        "byte_size": path.stat().st_size,
        "uri": str(path),
        "lifecycle": "observed",
        "manifest": manifest,
    }


class ArtifactRoundtripHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        artifact, path = _input_artifact(context, payload["input_artifact_id"], "commissioning_input")
        limit = context["commissioning_limits"]["max_artifact_input_bytes"]
        if artifact["byte_size"] > limit:
            raise SafetyError(f"commissioning input exceeds configured limit: {artifact['byte_size']} > {limit}")
        digest = hashlib.sha256()
        observed_bytes = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                observed_bytes += len(chunk)
        receipt = {
            "schema_version": "ninereeds_artifact_roundtrip_receipt_v1",
            "observed_at": _utc_now(),
            "run_id": context["run"]["id"],
            "input_artifact_id": artifact["id"],
            "input_kind": artifact["kind"],
            "input_sha256": digest.hexdigest(),
            "input_bytes": observed_bytes,
            "deployment_id": context["deployment"]["id"],
        }
        run_root = _run_root(context)
        output_path = run_root / "artifact-roundtrip-receipt.json"
        output_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return {
            "status": "succeeded",
            "artifacts": [_declaration("commissioning_receipt", output_path, receipt)],
            "metrics": {"input_bytes": observed_bytes, "input_sha256": digest.hexdigest()},
            "failure": None,
        }


class BoundedGPUProbeHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        limits = context["commissioning_limits"]
        devices = payload["device_indices"]
        matrix_size = payload["matrix_size"]
        iterations = payload["iterations"]
        duration_limit = payload["duration_limit_seconds"]
        if len(devices) > limits["gpu_max_devices"]:
            raise SafetyError("GPU probe requests too many devices")
        if matrix_size > limits["gpu_max_matrix_size"] or iterations > limits["gpu_max_iterations"]:
            raise SafetyError("GPU probe exceeds configured matrix or iteration limits")
        if duration_limit > limits["gpu_max_duration_seconds"]:
            raise SafetyError("GPU probe exceeds configured duration limit")
        estimated_bytes = 3 * matrix_size * matrix_size * 4
        if estimated_bytes > limits["gpu_max_allocated_bytes"]:
            raise SafetyError("GPU probe estimated tensor allocation exceeds configured limit")

        try:
            import torch
        except ImportError as exc:
            raise SafetyError("GPU probe runtime has no Torch package") from exc
        if not torch.cuda.is_available():
            raise SafetyError("CUDA is unavailable")
        if any(index >= torch.cuda.device_count() for index in devices):
            raise SafetyError("GPU probe names an unavailable device")
        observations = HealthcheckHandler._gpu_observation() or []
        temperatures = {item["index"]: item["temperature_c"] for item in observations}
        if any(temperatures.get(index, 0) > limits["gpu_max_start_temperature_c"] for index in devices):
            raise SafetyError("GPU probe refused because a selected device is too warm")

        started = time.monotonic()
        device_results = []
        for index in devices:
            if time.monotonic() - started >= duration_limit:
                raise SafetyError("GPU probe reached its duration bound before all devices ran")
            device = torch.device(f"cuda:{index}")
            torch.cuda.set_device(device)
            torch.cuda.reset_peak_memory_stats(device)
            torch.cuda.manual_seed(payload["seed"] + index)
            left = torch.randn((matrix_size, matrix_size), device=device, dtype=torch.float32)
            right = torch.randn((matrix_size, matrix_size), device=device, dtype=torch.float32)
            checksum = 0.0
            device_started = time.monotonic()
            for _ in range(iterations):
                product = left @ right
                checksum += float(product[0, 0].item())
                if time.monotonic() - started > duration_limit:
                    raise SafetyError("GPU probe exceeded its duration bound")
            torch.cuda.synchronize(device)
            elapsed = time.monotonic() - device_started
            peak = int(torch.cuda.max_memory_allocated(device))
            if peak > limits["gpu_max_allocated_bytes"]:
                raise SafetyError("GPU probe exceeded its allocated-memory bound")
            properties = torch.cuda.get_device_properties(device)
            device_results.append(
                {
                    "index": index,
                    "name": properties.name,
                    "iterations": iterations,
                    "matrix_size": matrix_size,
                    "elapsed_seconds": elapsed,
                    "peak_allocated_bytes": peak,
                    "checksum": checksum,
                    "start_temperature_c": temperatures.get(index),
                }
            )
            del left, right, product
            torch.cuda.empty_cache()
        total_elapsed = time.monotonic() - started
        if total_elapsed > duration_limit:
            raise SafetyError("GPU probe exceeded its duration bound")
        report = {
            "schema_version": "ninereeds_bounded_gpu_probe_v1",
            "observed_at": _utc_now(),
            "run_id": context["run"]["id"],
            "deployment_id": context["deployment"]["id"],
            "parameters": payload,
            "configured_limits": limits,
            "devices": device_results,
            "elapsed_seconds": total_elapsed,
            "model_loaded": False,
        }
        run_root = _run_root(context)
        output_path = run_root / "gpu-probe-report.json"
        output_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return {
            "status": "succeeded",
            "artifacts": [_declaration("gpu_probe_report", output_path, report)],
            "metrics": {"devices": device_results, "elapsed_seconds": total_elapsed},
            "failure": None,
        }
