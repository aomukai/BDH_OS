import argparse
import hashlib
import json

from image_registry.foundation_corpus_expansion import audit_acquisition, audit_curriculum


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def asset(path, slot, contract, dependencies=None):
    payload = path.read_bytes()
    return {
        "slot_id": slot,
        "contract_id": contract,
        "local_path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "depends_on": dependencies or [],
        "missing_dependencies": [],
    }


def test_acquisition_audit_accepts_exact_coverage(tmp_path):
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    image_a.write_bytes(b"a")
    image_b.write_bytes(b"b")
    contracts = tmp_path / "contracts.jsonl"
    ledger = tmp_path / "accepted.jsonl"
    report = tmp_path / "report.json"
    write_jsonl(contracts, [{"commission_id": "r0001"}])
    write_jsonl(ledger, [asset(image_a, "r0001-i01", "r0001"), asset(image_b, "r0001-i02", "r0001")])
    result = audit_acquisition(argparse.Namespace(
        contracts=contracts,
        ledger=[ledger],
        images_per_contract=2,
        max_image_reuse=4,
        output=report,
    ))
    assert result["passed"] is True
    assert json.loads(report.read_text(encoding="utf-8"))["contracts_with_exact_count"] == 1


def test_curriculum_audit_checks_dependency_order_and_manifests(tmp_path):
    curriculum = tmp_path / "curriculum"
    curriculum.mkdir()
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    image_a.write_bytes(b"a")
    image_b.write_bytes(b"b")
    contracts = [
        {"contract_id": "c1", "display_label": "dog", "part_of_speech": "noun", "teaching_sense": "a domesticated canine animal", "ordinal": 1, "depends_on": [], "missing_dependencies": []},
        {"contract_id": "c2", "display_label": "doghouse", "part_of_speech": "noun", "teaching_sense": "a small shelter made for a dog", "ordinal": 2, "depends_on": ["c1"], "missing_dependencies": []},
    ]
    assets = [asset(image_a, "c0001-i01", "c1"), asset(image_b, "c0002-i01", "c2", ["c1"])]
    edges = [{"dependency_contract_id": "c1", "target_contract_id": "c2"}]
    write_jsonl(curriculum / "teaching-contracts.jsonl", contracts)
    write_jsonl(curriculum / "accepted-assets.jsonl", assets)
    write_jsonl(curriculum / "dependency-edges.jsonl", edges)
    result = audit_curriculum(argparse.Namespace(
        curriculum=curriculum,
        images_per_contract=1,
        max_image_reuse=4,
        output=None,
    ))
    assert result["training_ready"] is True


def test_curriculum_audit_rejects_undefined_lexical_contract(tmp_path):
    curriculum = tmp_path / "curriculum"
    curriculum.mkdir()
    image = tmp_path / "a.png"
    image.write_bytes(b"a")
    write_jsonl(curriculum / "teaching-contracts.jsonl", [{
        "contract_id": "c1", "display_label": "over", "part_of_speech": "other",
        "teaching_sense": "above something", "ordinal": 1, "depends_on": [],
        "missing_dependencies": [],
    }])
    write_jsonl(curriculum / "accepted-assets.jsonl", [asset(image, "c0001-i01", "c1")])
    write_jsonl(curriculum / "dependency-edges.jsonl", [])
    try:
        audit_curriculum(argparse.Namespace(
            curriculum=curriculum, images_per_contract=1, max_image_reuse=4, output=None,
        ))
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("undefined lexical class must fail the curriculum audit")
