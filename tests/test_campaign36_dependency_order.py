from image_registry.campaign36_dependency_order import normalized, stable_topological_order


def test_normalized_strips_infinitive_and_gloss():
    assert normalized("to Paint") == "paint"
    assert normalized("sole (of foot)") == "sole"


def test_stable_topological_order_moves_dependency_first():
    contracts = [
        {"concept_id": "doghouse", "ordinal": 1},
        {"concept_id": "dog", "ordinal": 2},
        {"concept_id": "house", "ordinal": 3},
        {"concept_id": "tree", "ordinal": 4},
    ]
    edges = [
        {"dependency_concept_id": "dog", "target_concept_id": "doghouse"},
        {"dependency_concept_id": "house", "target_concept_id": "doghouse"},
    ]
    order = stable_topological_order(contracts, edges)
    assert order.index("dog") < order.index("doghouse")
    assert order.index("house") < order.index("doghouse")
    assert order.index("tree") == 3


def test_stable_topological_order_rejects_cycles():
    contracts = [{"concept_id": "a", "ordinal": 1}, {"concept_id": "b", "ordinal": 2}]
    edges = [
        {"dependency_concept_id": "a", "target_concept_id": "b"},
        {"dependency_concept_id": "b", "target_concept_id": "a"},
    ]
    try:
        stable_topological_order(contracts, edges)
    except ValueError as error:
        assert "cycle" in str(error)
    else:
        raise AssertionError("cycle was not rejected")
