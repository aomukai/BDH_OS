from __future__ import annotations

from types import SimpleNamespace

import pytest

torch = pytest.importorskip(
    "torch", reason="Campaign 36C organ tests require the Cortex environment"
)
from torch import nn

from campaign36c.bootstrap import (
    CAMPAIGN36C_MULTIMODAL_STUDENT_SCHEMA,
    Campaign36CStudent,
)
from campaign36c.organism import OrganismConfig
from cortex.config import CortexConfig
from cortex.intention import IntentionHead
from cortex.siglip2 import Siglip2ProjectorConfig, Siglip2VisualIngress
from meta.scripts.train_campaign36c_bootstrap import verify_complete_organ_set


WIDTH = 512


class _Tokenizer:
    pad_token_id = 0

    def __call__(self, texts, **_kwargs):
        batch = len(texts)
        return {
            "input_ids": torch.ones(batch, 1, dtype=torch.long),
            "attention_mask": torch.ones(batch, 1, dtype=torch.long),
        }

    def batch_decode(self, values, **_kwargs):
        return ["spoken" for _ in range(values.size(0))]


class _TextIngress(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Embedding(8, 16).requires_grad_(False).eval()
        self.projector = nn.Sequential(nn.LayerNorm(16), nn.Linear(16, WIDTH))

    def tokenize(self, texts):
        return _Tokenizer()(texts)

    def forward(self, input_ids, attention_mask, _token_type_ids=None):
        with torch.no_grad():
            states = self.encoder(input_ids)
        return self.projector(states), attention_mask


class _VisualIngress(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.config = Siglip2ProjectorConfig(
            receptor_width=16,
            cortex_width=WIDTH,
            observation_tokens=2,
            attention_heads=8,
        )
        self.receptor_source = "/attested/siglip2-snapshot"
        self.receptor = nn.Linear(3, 16).requires_grad_(False).eval()
        self.resampler = nn.Linear(16, WIDTH)

    def project_features(self, patch_states, patch_mask, _spatial_shapes):
        return self.resampler(patch_states), patch_mask

    def forward(self, images):
        pixels = torch.ones(len(images), 2, 3)
        with torch.no_grad():
            patches = self.receptor(pixels)
        return self.resampler(patches), torch.ones(
            len(images), 2, dtype=torch.bool
        )

    def ownership_report(self):
        return {
            "frozen_receptor_parameters": sum(
                parameter.numel() for parameter in self.receptor.parameters()
            ),
            "visual_receptor_trainable_parameters": sum(
                parameter.numel()
                for parameter in self.receptor.parameters()
                if parameter.requires_grad
            ),
            "trainable_resampler_parameters": sum(
                parameter.numel() for parameter in self.resampler.parameters()
            ),
            "receptor_parameters_with_gradients": sum(
                parameter.grad is not None for parameter in self.receptor.parameters()
            ),
        }


class _CausalRenderer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embedding = nn.Embedding(8, 16)
        self.output = nn.Linear(16, 8, bias=False)

    def get_input_embeddings(self):
        return self.embedding

    def forward(self, *, inputs_embeds, **_kwargs):
        return SimpleNamespace(logits=self.output(inputs_embeds))

    def generate(self, *, inputs_embeds, **_kwargs):
        return torch.ones(inputs_embeds.size(0), 1, dtype=torch.long)


class _Expression(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.tokenizer = _Tokenizer()
        self.model = _CausalRenderer().requires_grad_(False).eval()
        self.projector = nn.Sequential(nn.LayerNorm(WIDTH), nn.Linear(WIDTH, 16))

    def prefix_embeddings(self, intentions):
        return self.projector(intentions)

    def generate(self, intentions, **kwargs):
        return self.model.generate(
            inputs_embeds=self.prefix_embeddings(intentions), **kwargs
        )


class _Organism(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.core = nn.Linear(WIDTH, WIDTH)
        self.organism_config = OrganismConfig(
            width=WIDTH,
            core_layers=1,
            core_heads=8,
            core_multiplier=1,
            seed_ingress_cells=1,
        )
        self.ingress_uids = (0,)

    def continuity_parameters(self):
        return tuple(self.core.parameters())

    def think(self, observed, **_kwargs):
        state = self.core(observed)
        result = SimpleNamespace(
            state=state,
            telemetry={"unique_uid_count": 1},
        )
        return SimpleNamespace(root_state=state, result=result)


def _student() -> Campaign36CStudent:
    return Campaign36CStudent(
        _Organism(),
        _TextIngress(),
        _VisualIngress(),
        IntentionHead(WIDTH, num_tokens=2, num_heads=8),
        _Expression(),
        cortex_config=CortexConfig(),
        donor_identity={"role": "organ_initialization_only"},
    )


def _has_gradient(module: nn.Module) -> bool:
    return any(parameter.grad is not None for parameter in module.parameters())


def test_text_and_visual_organs_share_one_latent_organism_and_broca() -> None:
    student = _student()

    text = student.text_objective(
        "number",
        "number",
        claim_address="lexeme:0001:number",
        evidence_lineage=("lfm-encoder:number",),
        novelty=1.0,
    )
    assert text.modality == "text"
    assert text.thought.result.state.shape[-1] == WIDTH
    text.loss.backward()

    assert _has_gradient(student.ingress.projector)
    assert _has_gradient(student.organism.core)
    assert _has_gradient(student.intention)
    assert _has_gradient(student.expression.projector)
    assert not _has_gradient(student.ingress.encoder)
    assert not _has_gradient(student.vision.receptor)
    assert not _has_gradient(student.expression.model)

    student.zero_grad(set_to_none=True)
    image = student.visual_objective(
        (
            torch.randn(2, 16),
            torch.ones(2, dtype=torch.bool),
            torch.tensor([1, 2]),
        ),
        "number",
        claim_address="lexeme:0001:number",
        evidence_lineage=("siglip2:image",),
        novelty=1.0,
    )
    assert image.modality == "image"
    assert image.thought.result.state.shape[-1] == WIDTH
    image.loss.backward()

    assert _has_gradient(student.vision.resampler)
    assert _has_gradient(student.organism.core)
    assert _has_gradient(student.intention)
    assert _has_gradient(student.expression.projector)
    assert not _has_gradient(student.ingress.encoder)
    assert not _has_gradient(student.vision.receptor)
    assert not _has_gradient(student.expression.model)


def test_raw_images_reach_the_shared_organism_and_complete_state_is_persisted() -> None:
    student = _student()

    result = student.image_objective(
        object(),
        "image",
        claim_address="preflight:image",
        evidence_lineage=("siglip2:raw",),
        novelty=1.0,
    )
    state = student.shared_state()

    assert result.thought.result.state.shape == (1, 2, WIDTH)
    assert state["schema_version"] == CAMPAIGN36C_MULTIMODAL_STUDENT_SCHEMA
    assert "text_ingress_projector_state" in state
    assert "visual_resampler_state" in state
    assert "intention_state" in state
    assert "expression_projector_state" in state
    assert state["cortex_config"]["encoder_revision"] == CortexConfig().encoder_revision
    assert state["cortex_config"]["lfm_revision"] == CortexConfig().lfm_revision


def test_complete_organ_preflight_exercises_both_modalities_and_broca() -> None:
    report = verify_complete_organ_set(_student())

    assert report["status"] == "passed"
    assert report["latent_width"] == WIDTH
    assert report["text_observation_tokens"] == 1
    assert report["visual_observation_tokens"] == 2
    assert report["text_encoder_revision"] == CortexConfig().encoder_revision
    assert report["expression_revision"] == CortexConfig().lfm_revision
    assert report["visual_receptor_revision"] == Siglip2ProjectorConfig().receptor_revision
    assert report["ownership"]["text_encoder_trainable_parameters"] == 0
    assert report["ownership"]["visual_receptor_trainable_parameters"] == 0
    assert report["ownership"]["expression_renderer_trainable_parameters"] == 0


def test_real_siglip2_ingress_freezes_receptor_and_trains_only_resampler(
    monkeypatch,
) -> None:
    class Processor:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return cls()

        def __call__(self, *, images, **_kwargs):
            batch = len(images)
            return {
                "pixel_values": torch.ones(batch, 3),
                "pixel_attention_mask": torch.ones(batch, 2, dtype=torch.bool),
                "spatial_shapes": torch.tensor([[1, 2]] * batch),
            }

    class Receptor(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.project = nn.Linear(3, 16)

        def forward(
            self, *, pixel_values, attention_mask, spatial_shapes, **_kwargs
        ):
            assert attention_mask.shape == pixel_values.shape[:1] + (2,)
            assert spatial_shapes.shape == pixel_values.shape[:1] + (2,)
            patch = self.project(pixel_values).unsqueeze(1).expand(-1, 2, -1)
            return SimpleNamespace(last_hidden_state=patch)

    class Model:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return SimpleNamespace(vision_model=Receptor())

    monkeypatch.setitem(
        __import__("sys").modules,
        "transformers",
        SimpleNamespace(AutoModel=Model, AutoProcessor=Processor),
    )
    ingress = Siglip2VisualIngress(
        config=Siglip2ProjectorConfig(
            receptor_width=16,
            cortex_width=WIDTH,
            observation_tokens=2,
            attention_heads=8,
        ),
        receptor_snapshot="/attested/siglip2-snapshot",
        receptor_dtype=torch.float32,
    )

    observed, mask = ingress([object()])
    observed.sum().backward()

    assert observed.shape == (1, 2, WIDTH)
    assert mask.tolist() == [[True, True]]
    assert ingress.receptor_source == "/attested/siglip2-snapshot"
    assert not _has_gradient(ingress.receptor)
    assert _has_gradient(ingress.resampler)
