#!/usr/bin/env python3
"""Authenticated, serialized OpenAI-compatible vision inference on trainbox."""

from __future__ import annotations

import argparse
import base64
import binascii
import gc
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import io
import json
import os
from pathlib import Path
import threading
import time
from typing import Any

from mission_hub.config import load_config_bundle
from mission_hub.gpu_lock import GPUResourceBusy, gpu_resource


MAX_REQUEST_BYTES = 32 * 1024 * 1024
MODEL_IDS = {"gemma-4-e2b-visual", "gemma-4-e4b-visual"}


def _bearer(headers: Any) -> str:
    value = headers.get("Authorization", "")
    return value[7:] if value.startswith("Bearer ") else ""


def _decode_request(document: dict[str, Any]) -> tuple[str, bytes]:
    messages = document.get("messages")
    if not isinstance(messages, list) or len(messages) != 1:
        raise ValueError("exactly one user message is required")
    content = messages[0].get("content") if isinstance(messages[0], dict) else None
    if not isinstance(content, list):
        raise ValueError("multimodal message content is required")
    texts = [item.get("text") for item in content if isinstance(item, dict) and item.get("type") == "text"]
    images = [item.get("image_url", {}).get("url") for item in content if isinstance(item, dict) and item.get("type") == "image_url"]
    if len(texts) != 1 or not isinstance(texts[0], str) or len(images) != 1 or not isinstance(images[0], str):
        raise ValueError("exactly one text part and one image part are required")
    prefix, separator, encoded = images[0].partition(",")
    if not separator or not prefix.startswith("data:image/") or ";base64" not in prefix:
        raise ValueError("image must be an inline base64 data URL")
    try:
        pixels = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image base64 is invalid") from exc
    if not pixels or len(pixels) > 16 * 1024 * 1024:
        raise ValueError("image exceeds the commissioned byte bound")
    return texts[0], pixels


class VisionServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], *, bundle: Any, token: str):
        super().__init__(address, VisionHandler)
        self.bundle = bundle
        self.token = token
        self.state_root = bundle.machines["trainbox"]["state_root"]


class VisionHandler(BaseHTTPRequestHandler):
    server: VisionServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        supplied = _bearer(self.headers)
        if supplied and hmac.compare_digest(supplied, self.server.token):
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": {"message": "authentication required"}})
        return False

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(HTTPStatus.OK, {"ok": True, "service": "ninereeds-trainbox-vision"})
            return
        if self.path != "/v1/models":
            self._json(HTTPStatus.NOT_FOUND, {"error": {"message": "not found"}})
            return
        if not self._authorized():
            return
        data = []
        for model_id in sorted(MODEL_IDS):
            model = self.server.bundle.models[model_id]
            data.append({
                "id": model["exact_name"], "object": "model",
                "name": model["exact_name"],
                "description": "Private trainbox vision-language model.",
                "context_length": model["context_tokens"],
                "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
                "top_provider": {"max_completion_tokens": model["output_tokens"]},
            })
        self._json(HTTPStatus.OK, {"object": "list", "data": data})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._json(HTTPStatus.NOT_FOUND, {"error": {"message": "not found"}})
            return
        if not self._authorized():
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > MAX_REQUEST_BYTES:
                raise ValueError("request exceeds the commissioned byte bound")
            document = json.loads(self.rfile.read(size))
            model = next(
                value for key, value in self.server.bundle.models.items()
                if key in MODEL_IDS and value["exact_name"] == document.get("model")
            )
            prompt, pixels = _decode_request(document)
            maximum = min(int(document.get("max_tokens") or model["output_tokens"]), model["output_tokens"], 2048)
            with gpu_resource(self.server.state_root, wait=False):
                content = self._infer(model, prompt, pixels, maximum)
            self._json(HTTPStatus.OK, {
                "id": "ninereeds-vision-local", "object": "chat.completion",
                "model": model["exact_name"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            })
        except GPUResourceBusy as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": {"code": "gpu_busy", "message": str(exc)}})
        except StopIteration:
            self._json(HTTPStatus.BAD_REQUEST, {"error": {"message": "unknown model"}})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": {"message": str(exc)}})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": {"message": f"{type(exc).__name__}: {exc}"}})

    @staticmethod
    def _infer(model_config: dict[str, Any], prompt: str, pixels: bytes, maximum: int) -> str:
        torch = None
        processor = model = None
        try:
            import torch
            from PIL import Image
            from transformers import AutoModelForMultimodalLM, AutoProcessor
            from meta.scripts.visual_runtime import ask

            processor = AutoProcessor.from_pretrained(model_config["weights"], local_files_only=True)
            device = model_config["device"]
            if device == "auto":
                if torch.cuda.device_count() < 2:
                    raise RuntimeError("automatic placement requires two CUDA devices")
                placement = {"device_map": "balanced", "max_memory": {0: "10GiB", 1: "10GiB", "cpu": "32GiB"}}
            else:
                placement = {"device_map": {"": device}}
            model = AutoModelForMultimodalLM.from_pretrained(
                model_config["weights"], local_files_only=True, dtype=torch.bfloat16, **placement,
            ).eval()
            with Image.open(io.BytesIO(pixels)) as source:
                image = source.convert("RGB")
            parsed, _raw = ask(model, processor, image, prompt, maximum)
            return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        finally:
            del model, processor
            gc.collect()
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--token-file", required=True)
    args = parser.parse_args()
    token_path = Path(args.token_file)
    token = token_path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit("vision API token is unavailable or too short")
    bundle = load_config_bundle(args.config)
    server = VisionServer((args.bind, args.port), bundle=bundle, token=token)

    def connection_watchdog() -> None:
        while True:
            time.sleep(30)
            try:
                os.write(1, b"\n")
            except OSError:
                os._exit(0)

    threading.Thread(target=connection_watchdog, name="vision-api-ssh-watchdog", daemon=True).start()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
