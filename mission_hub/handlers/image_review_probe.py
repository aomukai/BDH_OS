"""Bounded, operator-approved Gemma image-review throughput probe."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import time
from typing import Any
import urllib.request

from ..errors import SafetyError
from .commissioning import _declaration, _run_root, _utc_now


MODEL_SHA256 = "f2c28b3dc4776931ac6f879e11f203dec637ea0f14267a86ec8f6165f63f293f"
MODEL_BYTES = 16947541728
PROJECTOR_SHA256 = "41926ed5f1403cf5add23b0684992805ea6f97253096132e769e65646b8cef9d"
PROJECTOR_BYTES = 1194828256
RUNTIME = Path("/home/aomukai/executor/runtimes/llama-cpp-turboquant-8a891f4b/build/bin/llama-server")
RUNTIME_LIB = RUNTIME.parent
NCCL_LIB = Path("/home/aomukai/.venvs/ninereeds-vision/lib/python3.12/site-packages/nvidia/nccl/lib")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _download(specification: dict[str, Any], destination: Path) -> None:
    expected = {MODEL_SHA256: MODEL_BYTES, PROJECTOR_SHA256: PROJECTOR_BYTES}
    if expected.get(specification["sha256"]) != specification["byte_size"]:
        raise SafetyError("model download is not one of the commissioned exact files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size == specification["byte_size"] and _sha256(destination) == specification["sha256"]:
            return
        raise SafetyError(f"existing model path has unexpected identity: {destination}")
    partial = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(specification["url"])
    if partial.exists():
        request.add_header("Range", f"bytes={partial.stat().st_size}-")
    mode = "ab" if partial.exists() else "wb"
    with urllib.request.urlopen(request, timeout=180) as response, partial.open(mode) as output:
        while chunk := response.read(8 * 1024 * 1024):
            output.write(chunk)
    if partial.stat().st_size != specification["byte_size"] or _sha256(partial) != specification["sha256"]:
        raise SafetyError(f"downloaded model identity mismatch: {specification['filename']}")
    os.chmod(partial, 0o440)
    os.replace(partial, destination)


def _fetch_images(images: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for item in images:
        path = root / f"{item['source_id']}.jpg"
        if not path.exists():
            partial = path.with_suffix(".jpg.partial")
            with urllib.request.urlopen(item["url"], timeout=90) as response, partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            os.replace(partial, path)
        if _sha256(path) != item["sha256"]:
            raise SafetyError(f"benchmark image hash mismatch: {item['source_id']}")
        result.append({**item, "path": str(path)})
    return result


def _start_server(model: Path, projector: Path, gpu: int, port: int, log: Path) -> subprocess.Popen:
    environment = dict(os.environ)
    environment["CUDA_VISIBLE_DEVICES"] = str(gpu)
    environment["LD_LIBRARY_PATH"] = f"{RUNTIME_LIB}:{NCCL_LIB}"
    handle = log.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            str(RUNTIME), "--model", str(model), "--mmproj", str(projector),
            "--host", "127.0.0.1", "--port", str(port), "--ctx-size", "4096",
            "--parallel", "1", "--split-mode", "none", "--main-gpu", "0",
            "--n-gpu-layers", "auto", "--fit", "on",
        ],
        env=environment, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True,
    )
    process._ninereeds_log_handle = handle  # type: ignore[attr-defined]
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        if process.poll() is not None:
            handle.flush()
            raise RuntimeError(f"llama server on GPU {gpu} exited during startup")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if response.status == 200:
                    return process
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"llama server on GPU {gpu} did not become ready")


def _stop_server(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    process._ninereeds_log_handle.close()  # type: ignore[attr-defined]


def _review(port: int, image: dict[str, Any], prompt: str) -> dict[str, Any]:
    pixels = base64.b64encode(Path(image["path"]).read_bytes()).decode("ascii")
    payload = {
        "model": "gemma-4-26b-a4b-it-q4km",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + pixels}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": 512, "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        document = json.load(response)
    return {
        "ordinal": image["ordinal"], "source_id": image["source_id"],
        "seconds": time.perf_counter() - started,
        "content": document["choices"][0]["message"]["content"], "usage": document.get("usage"),
    }


def _phase_report(wall: float, results: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [item["seconds"] for item in results]
    return {
        "images": len(results), "wall_seconds": wall, "images_per_minute": len(results) * 60 / wall,
        "mean_latency_seconds": statistics.mean(latencies),
        "median_latency_seconds": statistics.median(latencies), "results": results,
    }


def _single(model: Path, projector: Path, images: list[dict[str, Any]], prompt: str, root: Path) -> dict[str, Any]:
    server = _start_server(model, projector, 0, 8792, root / "single-server.log")
    try:
        _review(8792, images[0], prompt)
        started = time.perf_counter()
        results = [_review(8792, image, prompt) for image in images]
        wall = time.perf_counter() - started
    finally:
        _stop_server(server)
    return _phase_report(wall, results)


def _worker(port: int, images: list[dict[str, Any]], prompt: str) -> list[dict[str, Any]]:
    return [_review(port, image, prompt) for image in images]


def _dual(model: Path, projector: Path, images: list[dict[str, Any]], prompt: str, root: Path) -> dict[str, Any]:
    first = _start_server(model, projector, 0, 8792, root / "dual-gpu0-server.log")
    second = None
    try:
        second = _start_server(model, projector, 1, 8793, root / "dual-gpu1-server.log")
        _review(8792, images[0], prompt)
        _review(8793, images[1], prompt)
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            left = pool.submit(_worker, 8792, images[::2], prompt)
            right = pool.submit(_worker, 8793, images[1::2], prompt)
            results = left.result() + right.result()
        wall = time.perf_counter() - started
    finally:
        _stop_server(first)
        if second is not None:
            _stop_server(second)
    return _phase_report(wall, sorted(results, key=lambda item: item["ordinal"]))


class ImageReviewProbeHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if payload["model"]["sha256"] != MODEL_SHA256 or payload["projector"]["sha256"] != PROJECTOR_SHA256:
            raise SafetyError("probe requires the commissioned Gemma 4 26B Q4_K_M identities")
        if payload["warmup_ordinal"] not in {item["ordinal"] for item in payload["images"]}:
            raise SafetyError("warmup ordinal is absent from the image set")
        if not RUNTIME.is_file() or not NCCL_LIB.is_dir():
            raise SafetyError("commissioned llama.cpp runtime dependencies are unavailable")
        state_root = Path(context["state_root"])
        model_root = state_root / "models" / "gemma-4-26b-a4b-it-q4km-c099eb48"
        model = model_root / payload["model"]["filename"]
        projector = model_root / payload["projector"]["filename"]
        _download(payload["model"], model)
        _download(payload["projector"], projector)
        images = sorted(
            _fetch_images(payload["images"], state_root / "probe-images" / "benchmark-20"),
            key=lambda item: item["ordinal"],
        )
        run_root = _run_root(context)
        single = _single(model, projector, images, payload["prompt"], run_root)
        dual = _dual(model, projector, images, payload["prompt"], run_root)
        factor = dual["images_per_minute"] / single["images_per_minute"]
        report = {
            "schema_version": "ninereeds_image_review_probe_v1", "observed_at": _utc_now(),
            "run_id": context["run"]["id"], "deployment_id": context["deployment"]["id"],
            "model": {"path": str(model), "sha256": _sha256(model), "byte_size": model.stat().st_size},
            "projector": {"path": str(projector), "sha256": _sha256(projector), "byte_size": projector.stat().st_size},
            "single": single, "dual": dual, "dual_over_single": factor,
        }
        report_path = run_root / "image-review-probe-report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        combined_log = run_root / "image-review-probe.log"
        with combined_log.open("w", encoding="utf-8") as output:
            for name in ("single-server.log", "dual-gpu0-server.log", "dual-gpu1-server.log"):
                output.write(f"===== {name} =====\n")
                output.write((run_root / name).read_text(encoding="utf-8", errors="replace"))
                output.write("\n")
        return {
            "status": "succeeded",
            "artifacts": [
                _declaration("image_review_probe_report", report_path, {
                    "schema_version": report["schema_version"], "dual_over_single": factor,
                    "model_sha256": MODEL_SHA256, "image_count": len(images),
                }),
                _declaration("log", combined_log, {"schema_version": "ninereeds_image_review_probe_log_v1"}),
            ],
            "metrics": {"single_images_per_minute": single["images_per_minute"],
                        "dual_images_per_minute": dual["images_per_minute"], "dual_over_single": factor},
            "failure": None,
        }
