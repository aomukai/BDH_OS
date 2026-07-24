#!/usr/bin/env python3
"""Verify LFM loss, generation, and gradient flow from virtual intentions."""

from __future__ import annotations

import argparse
import json

import torch

from cortex.lfm import LFMExpressionCortex


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ninereeds-width", type=int, default=256)
    parser.add_argument("--intention-tokens", type=int, default=8)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=16)
    args = parser.parse_args()

    device = torch.device(args.device)
    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    cortex = LFMExpressionCortex(
        args.ninereeds_width,
        dtype=dtype,
        local_files_only=args.local_files_only,
    ).to(device)
    intentions = torch.randn(
        1,
        args.intention_tokens,
        args.ninereeds_width,
        device=device,
        requires_grad=True,
    )
    response = cortex.tokenizer(
        ["I am Ninereeds."],
        add_special_tokens=False,
        return_tensors="pt",
    )
    loss = cortex.response_loss(
        intentions,
        response["input_ids"],
        response.get("attention_mask"),
    )
    loss.backward()
    intention_grad = float(intentions.grad.abs().mean().detach().cpu())
    projector_grads = [
        parameter.grad
        for parameter in cortex.projector.parameters()
        if parameter.requires_grad and parameter.grad is not None
    ]
    projector_grad = (
        sum(float(grad.abs().mean().detach().cpu()) for grad in projector_grads) / len(projector_grads)
        if projector_grads
        else 0.0
    )
    frozen_model_grad_count = sum(parameter.grad is not None for parameter in cortex.model.parameters())

    generated = cortex.generate(
        intentions.detach(),
        max_new_tokens=args.max_new_tokens,
        do_sample=False,
    )
    decoded = cortex.tokenizer.batch_decode(generated, skip_special_tokens=True)
    report = {
        "schema_version": "lfm_intention_prefix_probe_v1",
        "loss": float(loss.detach().cpu()),
        "intention_gradient_mean_abs": intention_grad,
        "projector_gradient_mean_abs": projector_grad,
        "frozen_lfm_parameters_with_gradients": frozen_model_grad_count,
        "generated_token_shape": list(generated.shape),
        "decoded": decoded,
        "pass": bool(intention_grad > 0 and projector_grad > 0 and frozen_model_grad_count == 0),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
