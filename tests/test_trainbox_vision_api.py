from __future__ import annotations

import base64

import pytest

from meta.scripts.vision_api import _decode_request
from mission_hub.gpu_lock import GPUResourceBusy, gpu_resource


def test_vision_api_requires_exactly_one_inline_image() -> None:
    pixels = b"image-bytes"
    prompt, decoded = _decode_request({"messages": [{"role": "user", "content": [
        {"type": "text", "text": "caption"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(pixels).decode()}},
    ]}]})
    assert prompt == "caption"
    assert decoded == pixels


def test_gpu_resource_refuses_a_second_owner(tmp_path) -> None:
    with gpu_resource(tmp_path, wait=False):
        with pytest.raises(GPUResourceBusy):
            with gpu_resource(tmp_path, wait=False):
                pass
