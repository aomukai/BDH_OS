from image_registry.campaign36_infinitive_remediation import review_prompt


def test_review_prompt_binds_exact_sense():
    prompt = review_prompt({
        "display_label": "to pertain",
        "part_of_speech": "verb",
        "teaching_sense": "to be relevant to a situation",
    })
    assert "to pertain" in prompt
    assert "to be relevant to a situation" in prompt
    assert "another meaning of the same spelling" in prompt
