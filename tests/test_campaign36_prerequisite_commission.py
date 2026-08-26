from image_registry.campaign36_prerequisite_commission import lexical_key, make_groups


def test_lexical_key_merges_infinitive_surface():
    assert lexical_key("to Paint") == "paint"


def test_make_groups_preserves_distinct_claims():
    contracts = [
        {"contract_id": "source-c0001", "display_label": "nail", "part_of_speech": "noun", "teaching_sense": "metal", "ordinal": 1},
        {"contract_id": "source-c0002", "display_label": "to nail", "part_of_speech": "verb", "teaching_sense": "fasten", "ordinal": 2},
    ]
    missing = [
        {"component": "nail", "claim_id": "a", "target_contract_id": "x", "target_display_label": "fingernail", "target_original_ordinal": 1, "relation": "compound_component", "rationale": "body part"},
        {"component": "nail", "claim_id": "b", "target_contract_id": "y", "target_display_label": "to nail", "target_original_ordinal": 2, "relation": "derivational_base", "rationale": "fasten"},
    ]
    groups = make_groups(missing, contracts)
    assert len(groups) == 1
    assert len(groups[0]["claims"]) == 2
    assert len(groups[0]["existing_same_lexeme_contracts"]) == 2
