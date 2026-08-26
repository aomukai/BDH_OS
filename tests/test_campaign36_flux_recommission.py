from image_registry.campaign36_flux_recommission import seed_for


def test_recommission_seed_is_stable_and_namespaced() -> None:
    assert seed_for("a", "request") == seed_for("a", "request")
    assert seed_for("a", "request") != seed_for("b", "request")
