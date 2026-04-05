"""Compare base model vs QA behavior LoRA side by side.

Runs identical prompts with the same seed through both models
so the only variable is the LoRA.

Usage:
    python loras/skills/qa_behavior/test_lora.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bdh import BDH, BDHConfig  # noqa: E402
from inference import BDHInference  # noqa: E402

HERE = Path(__file__).resolve().parent
CHECKPOINT = ROOT / "core" / "bdh_100m_final.pt"
LORA_PATH  = HERE / "lora.pt"

# Prompts split by shape so we can see where the LoRA helps most
QA_PROMPTS = [
    "Q: What is a book?\nA:",
    "Q: What is a friend?\nA:",
    "Q: Why do birds sing?\nA:",
    "Q: Why do we sleep?\nA:",
    "Q: How does rain form?\nA:",
    "Q: How do fish breathe?\nA:",
]

DEFINITION_PROMPTS = [
    "A book is",
    "A school is",
    "An ocean is",
    "Language is",
]

OTHER_PROMPTS = [
    "Once upon a time there was a",
    "She opened the door and saw",
    "I am hungry because",
]

ALL_PROMPTS = QA_PROMPTS + DEFINITION_PROMPTS + OTHER_PROMPTS

SEEDS = [42 + i * 7 for i in range(len(ALL_PROMPTS))]
MAX_NEW_TOKENS = 60
TEMPERATURE    = 0.8
TOP_K          = None


# ---------------------------------------------------------------------------
# Load base model (reusable)
# ---------------------------------------------------------------------------

def load_base_model(device: torch.device) -> BDH:
    torch.serialization.add_safe_globals([BDHConfig])
    ckpt = torch.load(CHECKPOINT, map_location=device, weights_only=True)
    model = BDH(BDHConfig())
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    return model


# ---------------------------------------------------------------------------
# Apply / remove LoRA delta directly on model weights
# ---------------------------------------------------------------------------

def apply_lora(model: BDH, lora_state: dict) -> None:
    """Add LoRA delta to encoder and encoder_v in-place."""
    for param_name in ("encoder", "encoder_v"):
        s = lora_state[param_name]
        delta = (s["lora_A"].to(model.encoder.device)
                 @ s["lora_B"].to(model.encoder.device)) * s["scaling"]
        getattr(model, param_name).data.add_(delta)


def remove_lora(model: BDH, lora_state: dict) -> None:
    """Subtract LoRA delta to restore base weights."""
    for param_name in ("encoder", "encoder_v"):
        s = lora_state[param_name]
        delta = (s["lora_A"].to(model.encoder.device)
                 @ s["lora_B"].to(model.encoder.device)) * s["scaling"]
        getattr(model, param_name).data.sub_(delta)


# ---------------------------------------------------------------------------
# Seeded generation
# ---------------------------------------------------------------------------

def generate(model: BDH, prompt: str, seed: int, device: torch.device) -> str:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    token_ids = list(prompt.encode("utf-8", errors="replace"))
    idx = torch.tensor([token_ids], dtype=torch.long, device=device)

    with torch.no_grad():
        out = model.generate(idx, max_new_tokens=MAX_NEW_TOKENS,
                             temperature=TEMPERATURE, top_k=TOP_K)

    decoded = bytes(int(t) % 256 for t in out[0].tolist()).decode("utf-8", errors="replace")
    if decoded.startswith(prompt):
        return decoded[len(prompt):].strip() or decoded.strip()
    return decoded.strip()


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_base_model(device)
    lora_state = torch.load(LORA_PATH, map_location="cpu", weights_only=True)

    print(f"LoRA meta: {lora_state['meta']}\n")

    sections = [
        ("Q / A prompts  ← LoRA trained on these", QA_PROMPTS),
        ("Definition completions", DEFINITION_PROMPTS),
        ("Other completions  ← LoRA never saw these", OTHER_PROMPTS),
    ]

    prompt_index = 0
    for section_title, prompts in sections:
        print(f"\n{'='*65}")
        print(f"  {section_title}")
        print(f"{'='*65}")

        for prompt in prompts:
            seed = SEEDS[prompt_index]
            prompt_index += 1

            base_out = generate(model, prompt, seed, device)

            apply_lora(model, lora_state)
            lora_out = generate(model, prompt, seed, device)
            remove_lora(model, lora_state)

            display = prompt.replace("\n", "\\n")
            print(f"\n  prompt : {display!r}")
            print(f"  base   : {base_out!r}")
            print(f"  lora   : {lora_out!r}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora", type=Path, default=LORA_PATH,
                        help="Path to lora.pt (default: lora.pt in this directory)")
    args = parser.parse_args()
    LORA_PATH = args.lora
    main()
