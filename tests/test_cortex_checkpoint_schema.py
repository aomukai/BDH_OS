from __future__ import annotations

import torch
import pytest

from cortex.config import CORTEX_ARCHITECTURE, CortexConfig
from cortex.student import build_student


def test_lfm_encoder_is_the_default_cortex_architecture() -> None:
    config = CortexConfig()

    assert config.encoder_model_id == "LiquidAI/LFM2.5-Encoder-230M"
    assert config.encoder_width == 1024
    assert config.encoder_layer == -1
    assert config.encoder_max_length == 512
    assert CORTEX_ARCHITECTURE.startswith("lfm2_5_encoder_230m_frozen__")
    config.validate_for_ninereeds(512)


def test_archived_mbert_checkpoint_cannot_parent_lfm_encoder_lineage(
    tmp_path,
) -> None:
    checkpoint = tmp_path / "mbert-v1.pt"
    torch.save(
        {"schema_version": "ninereeds_cortex_checkpoint_v1"},
        checkpoint,
    )

    with pytest.raises(ValueError, match="mBERT Cortex v1 checkpoints are archived"):
        build_student(
            checkpoint,
            frozen_dtype=torch.bfloat16,
            local_files_only=True,
        )
