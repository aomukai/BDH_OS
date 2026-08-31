from __future__ import annotations

import torch

from campaign36c import Campaign36COrganism, OrganismConfig


def test_25m_embryo_has_exact_core_and_cell_ownership() -> None:
    organism = Campaign36COrganism.embryo()

    assert organism.core_parameter_count == 25_427_968
    assert organism.trainable_core_parameter_count == 25_165_824
    assert organism.tissue_parameter_count == 8 * 7_680
    assert tuple(organism.ingress_uids) == tuple(range(8))
    assert not organism.core.embed.weight.requires_grad
    assert not organism.core.lm_head.requires_grad


def test_embryo_initialization_is_deterministic_without_consuming_caller_rng() -> None:
    torch.manual_seed(91)
    expected = torch.rand(3)
    torch.manual_seed(91)
    first = Campaign36COrganism.embryo()
    observed = torch.rand(3)
    second = Campaign36COrganism.embryo()

    assert torch.equal(expected, observed)
    for left, right in zip(first.parameters(), second.parameters(), strict=True):
        assert torch.equal(left, right)


def test_disconnected_tissue_is_not_executed_or_credited() -> None:
    organism = Campaign36COrganism.embryo(
        OrganismConfig(seed_ingress_cells=2, core_layers=1, core_multiplier=1)
    )
    observation = torch.randn(1, 4, 512)

    thought = organism.think(
        observation,
        attention_mask=torch.ones(1, 4, dtype=torch.bool),
        novelty=1.0,
        claim_address="test:disconnected",
        evidence_lineage=("test:one",),
    )

    assert thought.result.telemetry["unique_uids"] == [0, 1]
    assert thought.result.telemetry["full_transforms"] == 2
    assert {item.uid for item in thought.result.eligibility} == {0, 1}


def test_bfloat16_inventory_reports_real_storage_bytes() -> None:
    organism = Campaign36COrganism.embryo(
        OrganismConfig(seed_ingress_cells=2, core_layers=1, core_multiplier=1)
    )
    inventory = organism.place(
        core_device="cpu",
        tissue_device="cpu",
        dtype=torch.bfloat16,
    )

    assert inventory["core"]["parameter_bytes"] == (
        inventory["core"]["parameters"] * 2
    )
    assert inventory["tissue"]["parameter_bytes"] == 2 * 2 * 7_680
    assert organism.core.attn.freqs.dtype == torch.float32


def test_bfloat16_placement_preserves_bdh_rotary_forward_contract() -> None:
    organism = Campaign36COrganism.embryo(
        OrganismConfig(seed_ingress_cells=1, core_layers=1, core_multiplier=1)
    )
    organism.place(
        core_device="cpu",
        tissue_device="cpu",
        dtype=torch.bfloat16,
    )

    thought = organism.think(
        torch.randn(1, 2, 512, dtype=torch.bfloat16),
        attention_mask=torch.ones(1, 2, dtype=torch.bool),
        novelty=1.0,
        claim_address="test:bfloat16-forward",
        evidence_lineage=("test:one",),
    )

    assert thought.root_state.dtype == torch.bfloat16
    assert thought.result.state.dtype == torch.bfloat16
