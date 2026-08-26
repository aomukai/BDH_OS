from pathlib import Path

from image_registry.campaign36_infinitive_generation import request_id


def test_request_id_is_stable_and_stage_specific():
    assert request_id("c0626-i01", "flux_1") == "c36-inf-c0626-i01-flux-1"
    assert request_id("c0626-i01", "flux_2") != request_id("c0626-i01", "flux_1")
    assert request_id("c1473-i03", "human_gpt_1").endswith("human-gpt-1")
    assert request_id("c1616-i09", "human_flux_1").endswith("human-flux-1")
