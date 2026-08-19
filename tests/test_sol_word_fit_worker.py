from image_benchmark.sol_word_fit_worker import FINAL_SCHEMA


def test_sol_final_judge_cannot_return_uncertain():
    verdict = FINAL_SCHEMA["properties"]["targets"]["items"]["properties"]["verdict"]
    assert verdict["enum"] == ["accept", "reject"]
