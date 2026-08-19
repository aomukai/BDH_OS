import hashlib
import json
from pathlib import Path

from image_registry.campaign35_hard_tail_luna import main


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_hard_tail_luna_accepts_exact_generated_residual(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "tail.png"
    image.write_bytes(b"reviewed-image")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    decisions = [{
        "slot_id": "c0001-i01", "concept_id": "aside", "word": "aside",
        "disposition": "target_not_visible", "source": "flux-v12",
        "asset_id": 9, "local_path": str(image), "sha256": digest,
    }]
    decisions.extend({
        "slot_id": f"c9999-i{index:05d}", "concept_id": "other", "word": "other",
        "disposition": "accepted", "asset_id": 10,
    } for index in range(1, 25_000))
    decision_path = tmp_path / "decisions.jsonl"
    inventory = tmp_path / "inventory.jsonl"
    _jsonl(decision_path, decisions)
    _jsonl(inventory, [{"concept_id": "aside", "word": "aside", "route": "single_image"}])

    monkeypatch.setattr(
        "image_registry.campaign35_hard_tail_luna.review",
        lambda *_args, **_kwargs: ({
            "reason": "One book is set apart.",
            "targets": [{"word": "aside", "verdict": "accept", "reason": "Clearly aside."}],
        }, {"transcript": "test"}),
    )
    output = tmp_path / "output"
    assert main([
        "--decisions", str(decision_path), "--inventory", str(inventory),
        "--source", "flux-v12", "--output", str(output),
    ]) == 0
    rows = [json.loads(line) for line in (output / "decisions.jsonl").read_text().splitlines()]
    assert len(rows) == 25_000
    assert rows[0]["disposition"] == "accepted"
    assert rows[0]["review_model"] == "gpt-5.6-luna"
    assert json.loads((output / "summary.json").read_text())["accepted_slots"] == 1
