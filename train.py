#!/usr/bin/env python3
"""BDH curriculum training script.

Trains the BDH model on a single phase of training data.  Each phase
builds on the previous one by loading the prior checkpoint before
continuing.

Usage examples
--------------
  # Train phase 1 from scratch:
  python train.py --phase 1

  # Train phase 2 starting from phase 1 checkpoint:
  python train.py --phase 2 --resume core/phase_1.pt

  # Train phase 3 with custom hypers:
  python train.py --phase 3 --resume core/phase_2.pt --epochs 20 --lr 5e-4

  # Use a specific output path:
  python train.py --phase 1 --output core/my_run.pt

Checkpoints
-----------
  Saved to: core/phase_{N}.pt  (unless --output overrides)

Scaling
-------
  Pass --scale to use a larger BDHConfig (n_layer=12, n_embd=512, n_head=8, ~100M).
  Pass --scale-150m to use per-layer weights at 6x256 (~150M).
  Scaling only makes sense for phase 1 from scratch.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.optim.lr_scheduler import CosineAnnealingLR

from bdh import BDH, BDHConfig

ROOT = Path(__file__).resolve().parent
DEFAULT_SEED = 1337

# ---------------------------------------------------------------------------
# Phase → data files mapping
# ---------------------------------------------------------------------------

PHASE_FILES: dict[int, list[str]] = {
    1: ["training_data/phase 1.md"],
    2: ["training_data/phase 2.md"],
    3: ["training_data/phase 3.md", "training_data/phase_3_ext.md"],
    4: [
        "training_data/phase_4.md",
        "training_data/phase_4_ext.md",
        "training_data/phase_4_ext2.md",
    ],
    5: ["training_data/phase_5_v1.md", "training_data/phase_5_v1_1.md"],
}

# Default hypers per phase (can be overridden with CLI flags)
PHASE_DEFAULTS: dict[int, dict] = {
    1: {"epochs": 40, "lr": 1e-3},
    2: {"epochs": 30, "lr": 5e-4},
    3: {"epochs": 30, "lr": 5e-4},
    4: {"epochs": 25, "lr": 3e-4},
    5: {"epochs": 25, "lr": 3e-4},
}

# Default BDHConfig (small — ~25M params)
SMALL_CONFIG = BDHConfig(
    n_layer=6,
    n_embd=256,
    n_head=4,
    mlp_internal_dim_multiplier=128,
    vocab_size=256,
)

# Larger config (~100M params) for scaling experiments
LARGE_CONFIG = BDHConfig(
    n_layer=12,
    n_embd=512,
    n_head=8,
    mlp_internal_dim_multiplier=128,
    vocab_size=256,
)

# Per-layer 6x model (~150M params)
XL_150M_CONFIG = BDHConfig(
    n_layer=6,
    n_embd=256,
    n_head=4,
    mlp_internal_dim_multiplier=128,
    vocab_size=256,
    per_layer_weights=True,
)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_text(paths: list[str]) -> bytes:
    """Load and concatenate text from one or more files (as raw bytes)."""
    chunks = []
    for p in paths:
        full = ROOT / p
        if not full.exists():
            raise FileNotFoundError(f"Training data not found: {full}")
        chunks.append(full.read_bytes())
    return b"\n".join(chunks)


def load_jsonl_examples(
    path: Path,
    response_delimiter: bytes,
    eot_byte: int,
) -> list[tuple[bytes, int]]:
    """Load JSONL into (sequence_bytes, response_start_idx) examples.

    Supported record shapes:
    - {"prompt": "...", "completion": "..."}
    - {"text": "...### Response:\\n..."}
    """
    if not path.exists():
        raise FileNotFoundError(f"JSONL data not found: {path}")

    examples: list[tuple[bytes, int]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            obj = json.loads(s)

            if "prompt" in obj and "completion" in obj:
                p = str(obj["prompt"]).encode("utf-8", errors="replace")
                c = str(obj["completion"]).encode("utf-8", errors="replace")
                if len(c) == 0:
                    continue
                seq = p + c + bytes([eot_byte])
                response_start = len(p)
                examples.append((seq, response_start))
                continue

            if "text" in obj:
                t = str(obj["text"]).encode("utf-8", errors="replace")
                pos = t.find(response_delimiter)
                if pos < 0:
                    raise ValueError(
                        f"{path}:{line_no}: missing response delimiter "
                        f"{response_delimiter!r} in 'text' field."
                    )
                response_start = pos + len(response_delimiter)
                if response_start >= len(t):
                    continue
                seq = t + bytes([eot_byte])
                examples.append((seq, response_start))
                continue

            raise ValueError(
                f"{path}:{line_no}: expected prompt/completion fields or a text field."
            )

    if not examples:
        raise ValueError(f"No usable examples loaded from {path}.")
    return examples


def estimate_windows_and_batches(
    n_tokens: int, block_size: int, batch_size: int
) -> tuple[int, int]:
    if block_size <= 0:
        raise ValueError(f"block_size must be > 0 (got {block_size}).")
    if batch_size <= 0:
        raise ValueError(f"batch_size must be > 0 (got {batch_size}).")
    if n_tokens <= block_size:
        raise ValueError(
            f"Not enough tokens for block_size={block_size}. "
            f"Need more than {block_size} bytes of data after tokenization, got {n_tokens}."
        )

    # Matches range(0, n_tokens - block_size, block_size)
    num_windows = (n_tokens - block_size + block_size - 1) // block_size
    n_batches = (num_windows + batch_size - 1) // batch_size
    return num_windows, n_batches


def make_batches(data: bytes, block_size: int, batch_size: int, device: torch.device):
    """Yield (x, y) tensors from raw byte data indefinitely (one epoch pass)."""
    ids = torch.tensor(list(data), dtype=torch.long)
    n_tokens = len(ids) - 1  # need at least one next-token
    _, n_batches = estimate_windows_and_batches(n_tokens, block_size, batch_size)

    # All possible start indices
    starts = torch.arange(0, n_tokens - block_size, block_size, dtype=torch.long)
    # Shuffle
    perm = torch.randperm(len(starts))
    starts = starts[perm]

    emitted = 0
    for i in range(0, len(starts), batch_size):
        batch_starts = starts[i : i + batch_size]
        if len(batch_starts) == 0:
            continue
        x = torch.stack([ids[int(s) : int(s) + block_size] for s in batch_starts]).to(device)
        y = torch.stack(
            [ids[int(s) + 1 : int(s) + block_size + 1] for s in batch_starts]
        ).to(device)
        emitted += 1
        yield x, y
    if emitted != n_batches:
        raise RuntimeError(
            f"Batch generation mismatch: expected {n_batches} batches, emitted {emitted}."
        )


def estimate_jsonl_batches(n_examples: int, batch_size: int) -> int:
    if n_examples <= 0:
        raise ValueError("Need at least one JSONL example to train.")
    if batch_size <= 0:
        raise ValueError(f"batch_size must be > 0 (got {batch_size}).")
    return (n_examples + batch_size - 1) // batch_size


def make_jsonl_batches(
    examples: list[tuple[bytes, int]],
    block_size: int,
    batch_size: int,
    device: torch.device,
    eot_byte: int,
    prompt_tail_bytes: int,
    prompt_loss_weight: float,
):
    """Yield (x, y, mask) for prompt/completion JSONL training.

    mask is a per-target loss weight vector:
    - completion/EOT tokens: 1.0
    - prompt tokens: prompt_loss_weight
    - padded tokens: 0.0
    """
    if block_size <= 0:
        raise ValueError(f"block_size must be > 0 (got {block_size}).")

    n = len(examples)
    order = torch.randperm(n).tolist()
    n_batches = estimate_jsonl_batches(n, batch_size)
    emitted = 0

    for i in range(0, n, batch_size):
        batch_ids = order[i : i + batch_size]
        xs: list[torch.Tensor] = []
        ys: list[torch.Tensor] = []
        ms: list[torch.Tensor] = []

        for j in batch_ids:
            seq, response_start = examples[j]
            seq_len = len(seq)
            if seq_len < 2:
                continue

            max_start = max(0, seq_len - (block_size + 1))
            desired_start = max(0, response_start - prompt_tail_bytes)
            start = min(desired_start, max_start)
            if response_start < start:
                start = min(response_start, max_start)

            win = seq[start : start + block_size + 1]
            orig_win_len = len(win)
            if orig_win_len < block_size + 1:
                win += bytes([eot_byte]) * (block_size + 1 - orig_win_len)

            x = torch.tensor(list(win[:-1]), dtype=torch.long)
            y = torch.tensor(list(win[1:]), dtype=torch.long)

            # y[k] predicts absolute byte at (start + k + 1)
            abs_targets = torch.arange(start + 1, start + block_size + 1, dtype=torch.long)
            valid = abs_targets < (start + orig_win_len)
            in_completion = abs_targets >= response_start
            prompt_valid = valid & (~in_completion)
            m = in_completion.to(torch.float32) + prompt_valid.to(torch.float32) * prompt_loss_weight

            xs.append(x)
            ys.append(y)
            ms.append(m)

        if not xs:
            continue

        emitted += 1
        yield torch.stack(xs).to(device), torch.stack(ys).to(device), torch.stack(ms).to(device)

    if emitted != n_batches:
        raise RuntimeError(
            f"JSONL batch generation mismatch: expected {n_batches}, emitted {emitted}."
        )


def count_params(model: BDH) -> int:
    return sum(p.numel() for p in model.parameters())


def set_reproducibility(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # Prefer reproducibility over peak speed so repeated runs are comparable.
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def load_checkpoint(path: Path, model: BDH, device: torch.device) -> None:
    """Load weights from a checkpoint into model in-place."""
    torch.serialization.add_safe_globals([BDHConfig])
    ckpt = torch.load(path, map_location=device, weights_only=True)
    if isinstance(ckpt, dict):
        state = (
            ckpt.get("model_state_dict")
            or ckpt.get("model")
            or ckpt.get("state_dict")
            or ckpt
        )
    else:
        raise TypeError(f"Unsupported checkpoint format: {type(ckpt)}")
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        print(f"  [warn] Missing keys: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    if unexpected:
        print(f"  [warn] Unexpected keys: {unexpected[:5]}{'...' if len(unexpected) > 5 else ''}")


def save_checkpoint(path: Path, model: BDH, config: BDHConfig, phase: int, epoch: int, loss: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "config": config,
            "phase": phase,
            "epoch": epoch,
            "loss": loss,
        },
        path,
    )


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train(
    phase: int,
    resume: Path | None,
    output: Path,
    epochs: int,
    lr: float,
    batch_size: int,
    block_size: int,
    seed: int,
    log_interval: int,
    grad_accum_steps: int,
    amp_bf16: bool,
    log_vram: bool,
    scale: bool,
    scale_150m: bool,
    jsonl_data: Path | None,
    mask_instruction_loss: bool,
    response_delimiter: bytes,
    eot_byte: int,
    prompt_tail_bytes: int,
    prompt_loss_weight: float,
    device: torch.device,
) -> None:
    print(f"\n{'='*60}")
    print(f"  BDH Phase {phase} Training")
    print(f"{'='*60}")

    # --- Data ---
    data_mode = "jsonl" if jsonl_data is not None else "phase_text"
    if data_mode == "jsonl":
        print(f"  JSONL data: {jsonl_data}")
        examples = load_jsonl_examples(
            path=jsonl_data,
            response_delimiter=response_delimiter,
            eot_byte=eot_byte,
        )
        print(f"  JSONL examples: {len(examples):,}")
        num_windows = len(examples)
        steps_per_epoch = estimate_jsonl_batches(len(examples), batch_size)
    else:
        paths = PHASE_FILES[phase]
        print(f"  Data files: {paths}")
        data = load_text(paths)
        print(f"  Total bytes: {len(data):,}")
        n_tokens = len(data) - 1
        num_windows, steps_per_epoch = estimate_windows_and_batches(
            n_tokens=n_tokens,
            block_size=block_size,
            batch_size=batch_size,
        )
    updates_per_epoch = (steps_per_epoch + grad_accum_steps - 1) // grad_accum_steps
    total_updates = epochs * updates_per_epoch

    # --- Model ---
    if scale_150m:
        config = XL_150M_CONFIG
        model_name = "xl-150m"
    elif scale:
        config = LARGE_CONFIG
        model_name = "large-100m"
    else:
        config = SMALL_CONFIG
        model_name = "small-25m"
    model = BDH(config).to(device)
    n_params = count_params(model)
    print(f"  Model: {model_name} ({n_params/1e6:.1f}M params)")

    if resume is not None:
        print(f"  Resuming from: {resume}")
        load_checkpoint(resume, model, device)
    else:
        print("  Training from scratch.")

    # --- Optimizer & scheduler ---
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.1)
    scheduler = CosineAnnealingLR(optimizer, T_max=total_updates, eta_min=lr * 0.1)

    print(f"  Seed: {seed}  |  Deterministic: enabled")
    print(
        f"  Epochs: {epochs}  |  Windows/epoch: {num_windows}  |  "
        f"Micro-steps/epoch: {steps_per_epoch}  |  "
        f"Optimizer updates/epoch: {updates_per_epoch}  |  "
        f"Total optimizer updates: {total_updates}  |  LR: {lr}"
    )
    print(f"  Block size: {block_size}  |  Batch size: {batch_size}")
    print(f"  Grad accumulation: {grad_accum_steps}")
    print(f"  AMP bf16: {'enabled' if amp_bf16 else 'disabled'}")
    if data_mode == "jsonl":
        print(f"  Data mode: jsonl")
        print(f"  Mask instruction loss: {'enabled' if mask_instruction_loss else 'disabled'}")
        print(f"  Response delimiter: {response_delimiter!r}")
        print(f"  EOT byte: {eot_byte}")
        print(f"  Prompt tail bytes: {prompt_tail_bytes}")
        print(f"  Prompt loss weight: {prompt_loss_weight}")
    else:
        print(f"  Data mode: phase_text")
    print(f"  VRAM logging: {'enabled' if log_vram else 'disabled'}")
    print(f"  Log interval: every {log_interval} step(s)")
    print(f"  Output: {output}")
    print()

    model.train()
    best_loss = float("inf")
    global_micro_step = 0  # 1-indexed in logs
    global_update_step = 0  # 1-indexed in logs
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        n_micro_steps = 0
        n_update_steps = 0
        t0 = time.time()
        optimizer.zero_grad(set_to_none=True)
        if log_vram and device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device=device)

        if data_mode == "jsonl":
            batch_iter = make_jsonl_batches(
                examples=examples,
                block_size=block_size,
                batch_size=batch_size,
                device=device,
                eot_byte=eot_byte,
                prompt_tail_bytes=prompt_tail_bytes,
                prompt_loss_weight=prompt_loss_weight,
            )
        else:
            batch_iter = make_batches(data, block_size, batch_size, device)

        for step_in_epoch, batch in enumerate(batch_iter, start=1):
            if data_mode == "jsonl":
                x, y, m = batch
            else:
                x, y = batch
                m = None

            with (
                torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                if amp_bf16 and device.type == "cuda"
                else contextlib.nullcontext()
            ):
                if data_mode == "jsonl" and mask_instruction_loss:
                    logits, _ = model(x, targets=None)
                    per_token = F.cross_entropy(
                        logits.reshape(-1, logits.size(-1)),
                        y.reshape(-1),
                        reduction="none",
                    )
                    mask_flat = m.reshape(-1)
                    valid = mask_flat.sum()
                    if valid.item() == 0:
                        continue
                    loss = (per_token * mask_flat).sum() / valid
                else:
                    _, loss = model(x, targets=y)

            raw_loss = float(loss.item())
            (loss / grad_accum_steps).backward()

            should_step = (
                step_in_epoch % grad_accum_steps == 0
                or step_in_epoch == steps_per_epoch
            )
            if should_step:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                n_update_steps += 1
                global_update_step += 1

            epoch_loss += raw_loss
            n_micro_steps += 1
            global_micro_step += 1

            if (
                step_in_epoch == 1
                or step_in_epoch % log_interval == 0
                or step_in_epoch == steps_per_epoch
            ):
                current_lr = scheduler.get_last_lr()[0]
                vram_str = ""
                if log_vram and device.type == "cuda":
                    alloc_mb = torch.cuda.memory_allocated(device=device) / (1024 * 1024)
                    reserved_mb = torch.cuda.memory_reserved(device=device) / (1024 * 1024)
                    peak_mb = torch.cuda.max_memory_allocated(device=device) / (1024 * 1024)
                    vram_str = (
                        f"  vram alloc/res/peak "
                        f"{alloc_mb:.0f}/{reserved_mb:.0f}/{peak_mb:.0f}MB"
                    )
                print(
                    f"    step {step_in_epoch:4d}/{steps_per_epoch} "
                    f"(global micro {global_micro_step:5d}/{epochs * steps_per_epoch}, "
                    f"update {global_update_step:5d}/{total_updates})  "
                    f"loss {raw_loss:.4f}  lr {current_lr:.2e}{vram_str}"
                )

        if n_micro_steps != steps_per_epoch:
            raise RuntimeError(
                f"Micro-step mismatch in epoch {epoch}: "
                f"expected {steps_per_epoch}, saw {n_micro_steps}."
            )
        if n_update_steps != updates_per_epoch:
            raise RuntimeError(
                f"Optimizer-step mismatch in epoch {epoch}: "
                f"expected {updates_per_epoch}, saw {n_update_steps}."
            )

        avg_loss = epoch_loss / max(n_micro_steps, 1)
        elapsed = time.time() - t0
        current_lr = scheduler.get_last_lr()[0]

        print(
            f"  epoch {epoch:3d}/{epochs}  "
            f"loss {avg_loss:.4f}  "
            f"lr {current_lr:.2e}  "
            f"({elapsed:.1f}s)"
        )

        if avg_loss < best_loss:
            best_loss = avg_loss
            save_checkpoint(output, model, config, phase, epoch, avg_loss)

    print(f"\n  Best loss: {best_loss:.4f}")
    print(f"  Checkpoint saved: {output}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def check_training_audit() -> None:
    """Verify that the final training audit has passed before starting."""
    audit_file = ROOT / "training_activation_audit.md"
    if not audit_file.exists():
        print("=" * 80)
        print("TRAINING BLOCKED: MISSING AUDIT FILE")
        print("=" * 80)
        print(f"Error: Audit file not found at: {audit_file}")
        print("Training cannot begin until the repo-wide audit is complete.")
        print("See `todo.md` for the final audit steps required.")
        sys.exit(1)

    content = audit_file.read_text()
    if "GO" not in content:
        print("=" * 80)
        print("TRAINING BLOCKED: AUDIT NOT PASSED")
        print("=" * 80)
        print(f"Error: Audit file found, but it is not in a 'GO' state.")
        print("The audit reported:")
        for line in content.splitlines():
            if "go / no-go" in line.lower():
                print(f"  > {line}")
        print("\nTraining cannot begin until the audit passes with a 'GO' status.")
        sys.exit(1)

    print("  Training audit: PASSED")


def main() -> None:
    # --- Audit check ---
    check_training_audit()

    parser = argparse.ArgumentParser(description="BDH curriculum trainer")
    parser.add_argument("--phase", type=int, required=True, choices=[1, 2, 3, 4, 5],
                        help="Training phase (1–5)")
    parser.add_argument("--resume", type=Path, default=None,
                        help="Checkpoint to load before training (for phases 2+)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output checkpoint path (default: core/phase_{N}.pt)")
    parser.add_argument("--epochs", type=int, default=None,
                        help="Number of epochs (overrides phase default)")
    parser.add_argument("--lr", type=float, default=None,
                        help="Learning rate (overrides phase default)")
    parser.add_argument("--batch-size", type=int, default=8,
                        help="Batch size (default: 8 — safe for 12GB GPU)")
    parser.add_argument("--block-size", type=int, default=256,
                        help="Context window in bytes (default: 256)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"Random seed (default: {DEFAULT_SEED})")
    parser.add_argument("--log-interval", type=int, default=25,
                        help="Per-step progress print frequency within each epoch (default: 25)")
    parser.add_argument("--grad-accum-steps", type=int, default=1,
                        help="Number of micro-batches to accumulate before optimizer step (default: 1)")
    parser.add_argument("--amp-bf16", action="store_true",
                        help="Enable CUDA AMP autocast with bfloat16")
    parser.add_argument("--log-vram", action="store_true",
                        help="Log CUDA VRAM usage during training progress updates")
    parser.add_argument("--allow-fresh-start", action="store_true",
                        help="Explicitly allow phase 2+ training without --resume")
    parser.add_argument("--jsonl-data", type=Path, default=None,
                        help="Optional prompt/completion JSONL training file (overrides phase text data)")
    parser.add_argument("--mask-instruction-loss", action="store_true",
                        help="In JSONL mode, compute loss only on completion tokens")
    parser.add_argument("--response-delimiter", type=str, default="### Response:\\n",
                        help="Delimiter used to locate completion start for JSONL text mode")
    parser.add_argument("--eot-byte", type=int, default=0,
                        help="End-of-example byte appended in JSONL mode (default: 0)")
    parser.add_argument("--prompt-tail-bytes", type=int, default=768,
                        help="In JSONL mode, include this many prompt bytes before response in each crop")
    parser.add_argument("--prompt-loss-weight", type=float, default=0.0,
                        help="In JSONL+mask mode, loss weight for prompt tokens (0.0 = hard mask)")
    parser.add_argument("--scale", action="store_true",
                        help="Use larger model config (~100M params)")
    parser.add_argument("--scale-150m", action="store_true",
                        help="Use per-layer 6x model config (~150M params)")
    parser.add_argument("--device", type=str, default=None,
                        help="Device: cpu / cuda / mps (auto-detected if omitted)")
    args = parser.parse_args()

    # Resolve defaults
    defaults = PHASE_DEFAULTS[args.phase]
    epochs = args.epochs if args.epochs is not None else defaults["epochs"]
    lr = args.lr if args.lr is not None else defaults["lr"]
    output = args.output if args.output is not None else ROOT / f"core/phase_{args.phase}.pt"
    if args.log_interval <= 0:
        parser.error("--log-interval must be > 0.")
    if args.grad_accum_steps <= 0:
        parser.error("--grad-accum-steps must be > 0.")
    if args.phase >= 2 and args.resume is None and not args.allow_fresh_start:
        parser.error(
            f"Phase {args.phase} requires --resume <checkpoint> to continue from prior phase. "
            "If you intentionally want to start fresh, add --allow-fresh-start."
        )
    if args.scale and args.scale_150m:
        parser.error("Choose only one scale mode: --scale or --scale-150m.")
    if args.resume is not None and not args.resume.exists():
        parser.error(f"--resume checkpoint not found: {args.resume}")
    if args.jsonl_data is not None and not args.jsonl_data.exists():
        parser.error(f"--jsonl-data not found: {args.jsonl_data}")
    if args.mask_instruction_loss and args.jsonl_data is None:
        parser.error("--mask-instruction-loss requires --jsonl-data.")
    if args.eot_byte < 0 or args.eot_byte > 255:
        parser.error("--eot-byte must be in [0, 255].")
    if args.prompt_tail_bytes < 0:
        parser.error("--prompt-tail-bytes must be >= 0.")
    if args.prompt_tail_bytes >= args.block_size:
        parser.error("--prompt-tail-bytes must be < --block-size.")
    if args.prompt_loss_weight < 0.0:
        parser.error("--prompt-loss-weight must be >= 0.")

    device = torch.device(
        args.device
        if args.device
        else ("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    )

    print(f"  Python: {sys.executable}")
    print(f"  Device: {device}")
    print(f"  Phase: {args.phase}")
    print(f"  Seed: {args.seed}")
    if args.amp_bf16 and device.type != "cuda":
        parser.error("--amp-bf16 requires --device cuda (or auto-selected cuda).")
    if args.resume is not None:
        print(f"  Resume checkpoint: {args.resume}")
    else:
        print("  Resume checkpoint: none (fresh start)")

    set_reproducibility(args.seed)

    train(
        phase=args.phase,
        resume=args.resume,
        output=output,
        epochs=epochs,
        lr=lr,
        batch_size=args.batch_size,
        block_size=args.block_size,
        seed=args.seed,
        log_interval=args.log_interval,
        grad_accum_steps=args.grad_accum_steps,
        amp_bf16=args.amp_bf16,
        log_vram=args.log_vram,
        scale=args.scale,
        scale_150m=args.scale_150m,
        jsonl_data=args.jsonl_data,
        mask_instruction_loss=args.mask_instruction_loss,
        response_delimiter=args.response_delimiter.encode("utf-8"),
        eot_byte=args.eot_byte,
        prompt_tail_bytes=args.prompt_tail_bytes,
        prompt_loss_weight=args.prompt_loss_weight,
        device=device,
    )


if __name__ == "__main__":
    main()
