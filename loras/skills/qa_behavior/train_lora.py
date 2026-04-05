"""Train the QA behavior micro LoRA for BDH.

Implements HebbianLoRA from the design doc using torch.nn.utils.parametrize,
which lets the LoRA delta flow through the existing BDH forward pass without
modifying bdh.py.

Trains only the LoRA parameters; all base model weights stay frozen.

Usage:
    python loras/skills/qa_behavior/train_lora.py
    python loras/skills/qa_behavior/train_lora.py --epochs 30 --rank 8 --lr 1e-3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.utils.parametrize as parametrize
from torch.optim import AdamW

# Repo root on sys.path so we can import bdh and inference
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bdh import BDH, BDHConfig  # noqa: E402

HERE = Path(__file__).resolve().parent
CHECKPOINT = ROOT / "core" / "bdh_100m_final.pt"
TRAIN_DATA = HERE / "train.jsonl"
OUTPUT_LORA = HERE / "lora.pt"


# ---------------------------------------------------------------------------
# HebbianLoRA — exactly as described in the design doc
# ---------------------------------------------------------------------------

class HebbianLoRA(nn.Module):
    """Deep LoRA — applied to encoder / encoder_v (global latent bias)."""

    def __init__(self, shape: tuple[int, int, int], rank: int = 8) -> None:
        super().__init__()
        nh, D, N = shape
        self.lora_A = nn.Parameter(torch.randn(nh, D, rank) * 0.02)
        self.lora_B = nn.Parameter(torch.zeros(nh, rank, N))
        self.scaling = 1.0 / rank

    def forward(self, base: torch.Tensor) -> torch.Tensor:
        return base + (self.lora_A @ self.lora_B) * self.scaling


class SurfaceLoRA(nn.Module):
    """Surface LoRA — applied to lm_head (output token shaping).

    Operates at the final projection layer only: shapes which tokens get
    promoted at output without touching the latent representation space.
    Low risk, independent of the deep LoRA.
    """

    def __init__(self, shape: tuple[int, int], rank: int = 4) -> None:
        super().__init__()
        D_in, D_out = shape
        self.lora_A = nn.Parameter(torch.randn(D_in, rank) * 0.02)
        self.lora_B = nn.Parameter(torch.zeros(rank, D_out))
        self.scaling = 1.0 / rank

    def forward(self, base: torch.Tensor) -> torch.Tensor:
        return base + (self.lora_A @ self.lora_B) * self.scaling


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def encode(text: str) -> list[int]:
    return list(text.encode("utf-8", errors="replace"))


def make_batch(prompt: str, completion: str, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    """Return (input_ids, targets) with prompt positions masked to -100."""
    p_ids = encode(prompt)
    c_ids = encode(completion)
    full = p_ids + c_ids

    input_ids = torch.tensor(full[:-1], dtype=torch.long, device=device).unsqueeze(0)

    # Targets: -100 for all prompt positions, then completion tokens
    targets_list = [-100] * (len(p_ids) - 1) + full[len(p_ids):]
    targets = torch.tensor(targets_list, dtype=torch.long, device=device).unsqueeze(0)

    return input_ids, targets


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def load_base_model(device: torch.device) -> BDH:
    torch.serialization.add_safe_globals([BDHConfig])
    ckpt = torch.load(CHECKPOINT, map_location=device, weights_only=True)
    model = BDH(BDHConfig())
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    return model


def attach_loras(
    model: BDH, rank: int, surface: bool = False
) -> tuple[HebbianLoRA, HebbianLoRA, SurfaceLoRA | None]:
    """Freeze base model, attach LoRA parametrizations.

    Always attaches deep LoRAs to encoder + encoder_v.
    Optionally attaches a surface LoRA to lm_head.
    """
    for p in model.parameters():
        p.requires_grad = False

    dev = next(model.parameters()).device

    lora_enc = HebbianLoRA(tuple(model.encoder.shape), rank=rank).to(dev)
    lora_enc_v = HebbianLoRA(tuple(model.encoder_v.shape), rank=rank).to(dev)
    parametrize.register_parametrization(model, "encoder",   lora_enc)
    parametrize.register_parametrization(model, "encoder_v", lora_enc_v)

    lora_surface = None
    if surface:
        lora_surface = SurfaceLoRA(tuple(model.lm_head.shape), rank=4).to(dev)
        parametrize.register_parametrization(model, "lm_head", lora_surface)

    return lora_enc, lora_enc_v, lora_surface


def count_trainable(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def save_lora(
    lora_enc: HebbianLoRA,
    lora_enc_v: HebbianLoRA,
    path: Path,
    meta: dict,
    lora_surface: SurfaceLoRA | None = None,
) -> None:
    state = {
        "encoder":   {
            "lora_A":  lora_enc.lora_A.data.cpu(),
            "lora_B":  lora_enc.lora_B.data.cpu(),
            "scaling": lora_enc.scaling,
        },
        "encoder_v": {
            "lora_A":  lora_enc_v.lora_A.data.cpu(),
            "lora_B":  lora_enc_v.lora_B.data.cpu(),
            "scaling": lora_enc_v.scaling,
        },
        "meta": meta,
    }
    if lora_surface is not None:
        state["lm_head"] = {
            "lora_A":  lora_surface.lora_A.data.cpu(),
            "lora_B":  lora_surface.lora_B.data.cpu(),
            "scaling": lora_surface.scaling,
        }
    torch.save(state, path)


def train(
    epochs: int = 20,
    rank: int = 8,
    lr: float = 1e-3,
    weight_decay: float = 0.01,
    checkpoint_every: int = 0,
    surface: bool = False,
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    data = load_data(TRAIN_DATA)
    print(f"Training examples: {len(data)}")

    model = load_base_model(device)
    lora_enc, lora_enc_v, lora_surface = attach_loras(model, rank, surface=surface)
    model.train()

    trainable = count_trainable(model)
    total = sum(p.numel() for p in model.parameters())
    surface_note = " + surface lm_head" if surface else ""
    print(f"Trainable parameters: {trainable:,} / {total:,} ({100*trainable/total:.2f}%){surface_note}")

    optimizer = AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=lr,
        weight_decay=weight_decay,
    )

    print(f"\nTraining for {epochs} epochs...\n")

    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        for ex in data:
            input_ids, targets = make_batch(ex["prompt"], ex["completion"], device)

            optimizer.zero_grad()
            logits, _ = model(input_ids)

            # Flatten and compute loss, ignoring -100 positions
            loss = torch.nn.functional.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=-100,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], max_norm=1.0
            )
            optimizer.step()
            epoch_loss += loss.item()

        avg = epoch_loss / len(data)
        if epoch % 5 == 0 or epoch == 1:
            delta_norm = (lora_enc.lora_A @ lora_enc.lora_B).norm().item() * lora_enc.scaling
            print(f"  Epoch {epoch:3d}/{epochs}  loss {avg:.4f}  delta_norm {delta_norm:.3f}")

        if checkpoint_every > 0 and epoch % checkpoint_every == 0:
            ckpt_path = OUTPUT_LORA.parent / f"lora_epoch{epoch:03d}.pt"
            meta = {
                "rank": rank, "epoch": epoch, "epochs": epochs, "lr": lr,
                "train_examples": len(data), "lora_type": "hebbian",
                "target_params": ["encoder", "encoder_v"] + (["lm_head"] if surface else []),
                "skill": "qa_behavior",
            }
            save_lora(lora_enc, lora_enc_v, ckpt_path, meta, lora_surface)
            print(f"             checkpoint → {ckpt_path.name}")

    meta = {
        "rank": rank, "epochs": epochs, "lr": lr,
        "train_examples": len(data), "lora_type": "hebbian",
        "target_params": ["encoder", "encoder_v"] + (["lm_head"] if surface else []),
        "skill": "qa_behavior",
    }
    save_lora(lora_enc, lora_enc_v, OUTPUT_LORA, meta, lora_surface)
    print(f"\nLoRA saved to {OUTPUT_LORA}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train QA behavior HebbianLoRA")
    parser.add_argument("--epochs",           type=int,   default=20)
    parser.add_argument("--rank",             type=int,   default=8)
    parser.add_argument("--lr",               type=float, default=1e-3)
    parser.add_argument("--weight-decay",     type=float, default=0.01)
    parser.add_argument("--checkpoint-every", type=int,   default=0,
                        help="Save a checkpoint every N epochs (0 = disabled).")
    parser.add_argument("--surface", action="store_true",
                        help="Also train a surface LoRA on lm_head.")
    args = parser.parse_args()

    train(
        epochs=args.epochs,
        rank=args.rank,
        lr=args.lr,
        weight_decay=args.weight_decay,
        checkpoint_every=args.checkpoint_every,
        surface=args.surface,
    )
