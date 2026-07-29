#!/usr/bin/env python3
"""Verify bidirectional LFM ingress does not corrupt causal LFM expression."""

from __future__ import annotations

import json

import torch
from safetensors import safe_open
from transformers.utils import cached_file

from cortex.lfm import LFMExpressionCortex
from cortex.lfm_encoder import LFMEncoderIngress


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frozen_dtype = torch.bfloat16
    width = 16
    ingress = LFMEncoderIngress(
        width,
        dtype=frozen_dtype,
        local_files_only=True,
    )
    restored_after_load = ingress.causal_runtime_is_restored()
    expression = LFMExpressionCortex(
        width,
        dtype=frozen_dtype,
        local_files_only=True,
    )
    weights_path = cached_file(
        ingress.config.encoder_model_id,
        "model.safetensors",
        revision=ingress.config.encoder_revision,
        local_files_only=True,
    )
    with safe_open(weights_path, framework="pt", device="cpu") as weights:
        checkpoint_embedding = weights.get_tensor("lfm2.embed_tokens.weight")
    loaded_embedding = ingress.encoder.embed_tokens.weight.detach().cpu()
    checkpoint_tensor_matches = torch.equal(
        loaded_embedding,
        checkpoint_embedding.to(dtype=loaded_embedding.dtype),
    )
    ingress.encoder.to(device)
    ingress.projector.to(device=device, dtype=frozen_dtype)
    expression.to(device=device, dtype=frozen_dtype)

    encoded = ingress.tokenize(
        [
            "The dog is not inside the box.",
            "犬は箱の中にいません。",
        ]
    )
    projected, attention_mask = ingress(
        encoded["input_ids"],
        encoded["attention_mask"],
        encoded.get("token_type_ids"),
    )
    restored_after_forward = ingress.causal_runtime_is_restored()

    intentions = torch.randn(
        2,
        8,
        width,
        device=device,
        dtype=frozen_dtype,
        requires_grad=True,
    )
    responses = expression.tokenizer(
        ["The dog is outside.", "犬は外にいます。"],
        add_special_tokens=False,
        padding=True,
        return_tensors="pt",
    )
    loss = expression.response_loss(
        intentions,
        responses["input_ids"],
        responses.get("attention_mask"),
    )
    loss.backward()
    encoder_gradients = sum(
        parameter.grad is not None for parameter in ingress.encoder.parameters()
    )
    expression_gradients = sum(
        parameter.grad is not None for parameter in expression.model.parameters()
    )
    projector_gradients = sum(
        parameter.grad is not None for parameter in expression.projector.parameters()
    )
    report = {
        "schema_version": "lfm_encoder_causal_coexistence_probe_v1",
        "device": str(device),
        "projected_shape": list(projected.shape),
        "attention_mask_shape": list(attention_mask.shape),
        "loss": float(loss.detach().to(torch.float32).cpu()),
        "restored_after_load": restored_after_load,
        "restored_after_forward": restored_after_forward,
        "checkpoint_tensor_matches": checkpoint_tensor_matches,
        "encoder_parameters_with_gradients": encoder_gradients,
        "expression_parameters_with_gradients": expression_gradients,
        "expression_projector_parameters_with_gradients": projector_gradients,
        "intention_gradients": intentions.grad is not None,
    }
    report["pass"] = (
        projected.shape[:2] == attention_mask.shape
        and projected.shape[-1] == width
        and torch.isfinite(loss).item()
        and restored_after_load
        and restored_after_forward
        and checkpoint_tensor_matches
        and encoder_gradients == 0
        and expression_gradients == 0
        and projector_gradients > 0
        and intentions.grad is not None
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
