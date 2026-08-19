import json
from pathlib import Path

from image_registry.campaign35_visual_completion import main


def _jsonl(path: Path, values: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in values), encoding="utf-8")


def _contract(tmp_path: Path, route: str) -> tuple[Path, Path, Path]:
    requirements = tmp_path / "requirements.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    inventory = tmp_path / "inventory.jsonl"
    slots = [f"c0001-i{index:05d}" for index in range(25_000)]
    _jsonl(requirements, [{"slot_id": slot, "concept_id": "concept", "word": "concept"} for slot in slots])
    _jsonl(decisions, [{"slot_id": slot, "concept_id": "concept", "word": "concept",
                        "disposition": "missing_candidate"} for slot in slots])
    _jsonl(inventory, [{"concept_id": "concept", "word": "concept", "route": route,
                        "source_path": "curriculum.md"}])
    return requirements, decisions, inventory


def test_nonstill_disposition_completes_exact_partition(tmp_path: Path) -> None:
    requirements, decisions, inventory = _contract(tmp_path, "not_visually_teachable")
    output = tmp_path / "output"
    assert main([
        "--db", str(tmp_path / "registry.sqlite3"), "--requirements", str(requirements),
        "--decisions", str(decisions), "--gap-inventory", str(inventory),
        "--output", str(output),
    ]) == 0
    report = json.loads((output / "validation_report.json").read_text())
    assert report["status"] == "task_complete"
    assert report["representation_disposition_slots"] == 25_000
    assert report["unresolved_teachable_items"] == 0


def test_single_image_residual_prevents_completion(tmp_path: Path) -> None:
    requirements, decisions, inventory = _contract(tmp_path, "single_image")
    output = tmp_path / "output"
    assert main([
        "--db", str(tmp_path / "registry.sqlite3"), "--requirements", str(requirements),
        "--decisions", str(decisions), "--gap-inventory", str(inventory),
        "--output", str(output),
    ]) == 2
    report = json.loads((output / "validation_report.json").read_text())
    assert report["status"] == "incomplete"
    assert report["unresolved_teachable_items"] == 25_000


def test_generation_identity_is_scoped_to_each_cycle_ledger(tmp_path: Path) -> None:
    requirements, decisions, inventory = _contract(tmp_path, "text_only")
    ledgers = []
    for cycle, digest in ((2, "a" * 64), (3, "b" * 64)):
        ledger = tmp_path / f"cycle-{cycle}.jsonl"
        _jsonl(ledger, [{
            "production_brief_id": "scene-0001", "variant_index": 0, "sha256": digest,
        }])
        ledgers.append(ledger)
    output = tmp_path / "output"
    assert main([
        "--db", str(tmp_path / "registry.sqlite3"), "--requirements", str(requirements),
        "--decisions", str(decisions), "--gap-inventory", str(inventory),
        "--flux-ledger", str(ledgers[0]), "--flux-ledger", str(ledgers[1]),
        "--output", str(output),
    ]) == 0
    assert json.loads((output / "validation_report.json").read_text())["flux_generated_assets"] == 2
