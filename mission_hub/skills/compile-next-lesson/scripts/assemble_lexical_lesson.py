#!/usr/bin/env python3
"""Deterministically assemble an early lexical lesson from accepted phased artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve()))


def binding(role: str, path: Path) -> dict[str, str]:
    return {"role": role, "path": rel(path), "sha256": sha(path)}


def bank_asset_id(label: str, ordinal: int) -> str:
    return f"bank-{label}-{ordinal:02d}"


def story_asset_id(page_number: int) -> str:
    return f"story-page-{page_number:02d}"


def control_for_open_label() -> dict[str, Any]:
    return {
        "machine_action": "SHOW_IMAGE_RECORD_BARE_LABEL",
        "spoken_text": None,
        "semantic_task": "record_bare_label_for_shown_image",
        "demonstrations": [],
        "options": [],
    }


def visible_wrong_label(stage_item: dict[str, Any]) -> str:
    """Resolve the frozen mismatch label from the accepted language-stage roles."""
    roles = stage_item.get("stimulus_asset_roles", [])
    values = [role.split(":", 1)[1] for role in roles if role.startswith("visible-wrong-label:")]
    if len(values) != 1 or values[0] == stage_item.get("target_label"):
        raise ValueError(f"{stage_item.get('id')}: requires one distinct visible-wrong-label role")
    return values[0]


def final_exercise(stage_item: dict[str, Any], asset_ordinal: int, labels: list[str]) -> dict[str, Any]:
    target = stage_item["target_label"]
    family_action = stage_item["machine_action"]
    target_asset = bank_asset_id(target, asset_ordinal)
    invariants = list(stage_item["semantic_invariants"])
    if stage_item["response_mode"] == "bare_label":
        return {
            "id": stage_item["id"],
            "teacher_text": "MACHINE_CONTROL",
            "expected_answers": list(stage_item["expected_answers"]),
            "invariants": invariants,
            "asset_ids": [target_asset],
            "target_language_required": True,
            "response_mode": "bare_label",
            "speaker_identity": "Ninereeds",
            "evidence_use": "learner_label_and_concept",
            "nonverbal_control": control_for_open_label(),
        }

    semantic_tasks = {
        "SHOW_LABEL_SELECT_MATCHING_IMAGE": "select_image_matching_displayed_bare_label",
        "SHOW_MISMATCH_SELECT_REPLACEMENT": "select_bare_label_replacing_visible_mismatch",
        "SHOW_IMAGE_SELECT_ONE_OF_TWO_LABELS": "select_bare_label_matching_displayed_image",
    }
    options: list[dict[str, Any]] = []
    assets = [target_asset]
    if family_action == "SHOW_LABEL_SELECT_MATCHING_IMAGE":
        for role in stage_item["stimulus_asset_roles"]:
            if not role.startswith("option-image:"):
                continue
            option_parts = role.split(":")[1:]
            exact_label_index = next((index for index, part in enumerate(option_parts) if part in labels), None)
            option_component_id = option_parts[0]
            option_label = (
                option_parts[exact_label_index]
                if exact_label_index is not None
                else next((label for label in labels if option_component_id.endswith(f"-{label}")), None)
            )
            if option_label is None:
                raise ValueError(f"cannot resolve image option label from {role}")
            option_asset = bank_asset_id(option_label, asset_ordinal)
            if option_asset not in assets:
                assets.append(option_asset)
            option_id = (
                "option-image:" + ":".join(option_parts[: exact_label_index + 1])
                if exact_label_index is not None
                else f"option-image:{option_component_id}"
            )
            options.append({"id": option_id, "display_kind": "image", "display_value": None, "asset_id": option_asset})
    else:
        for label in stage_item["option_labels"]:
            options.append({"id": label, "display_kind": "label", "display_value": label, "asset_id": None})
    control = {
        "machine_action": family_action,
        "spoken_text": None,
        "semantic_task": semantic_tasks[family_action],
        "demonstrations": [],
        "options": options,
    }
    if family_action == "SHOW_MISMATCH_SELECT_REPLACEMENT":
        control["displayed_mismatch_label"] = visible_wrong_label(stage_item)
    return {
        "id": stage_item["id"],
        "teacher_text": "MACHINE_CONTROL",
        "expected_answers": list(stage_item["expected_answers"]),
        "invariants": invariants,
        "asset_ids": assets,
        "target_language_required": False,
        "response_mode": "lexical_selection",
        "speaker_identity": None,
        "evidence_use": "concept_only_nonverbal",
        "nonverbal_control": control,
    }


def model_exercise(block: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    assets = [bank_asset_id(label, 1) for label in labels]
    worked_items = []
    for item in block["items"]:
        target = item["label"]
        target_index = labels.index(target)
        set_start = (target_index // 4) * 4
        distractor = labels[set_start + ((target_index - set_start + 1) % 4)]
        worked = {
            "label": target,
            "asset_id": bank_asset_id(target, 1),
            "machine_action": item["machine_action"],
            "feedback_action": "SHOW_CORRECT_OPTION",
        }
        if block["gate"] == "affirmative":
            worked["displayed_label"] = target
            worked["options"] = [
                {"id": f"worked-{block['id']}-{target}", "display_kind": "image", "asset_id": bank_asset_id(target, 1)},
                {"id": f"worked-{block['id']}-{distractor}", "display_kind": "image", "asset_id": bank_asset_id(distractor, 1)},
            ]
            worked["correct_option_id"] = f"worked-{block['id']}-{target}"
            worked["action_sequence"] = ["SHOW_BARE_LABEL", "SHOW_TWO_IMAGE_OPTIONS", "SHOW_CORRECT_OPTION"]
        elif block["gate"] == "negative":
            roles = [item.get("asset_role", "")]
            wrong = [role.split(":visible-wrong-label:", 1)[1] for role in roles if ":visible-wrong-label:" in role]
            if len(wrong) != 1 or wrong[0] == item["label"]:
                raise ValueError(f"{block['id']}: negative worked item requires a frozen distinct mismatch label")
            worked["displayed_mismatch_label"] = wrong[0]
            worked["options"] = [
                {"id": wrong[0], "display_kind": "label", "display_value": wrong[0]},
                {"id": target, "display_kind": "label", "display_value": target},
            ]
            worked["correct_option_id"] = target
            worked["action_sequence"] = ["SHOW_IMAGE_WITH_WRONG_LABEL", "SHOW_TWO_LABEL_OPTIONS", "SHOW_CORRECT_OPTION"]
        elif block["gate"] == "W_question":
            worked["options"] = []
            worked["correct_recorded_answer"] = target
            worked["action_sequence"] = ["SHOW_IMAGE_WITHOUT_LABEL", "RECORD_BARE_LABEL", "SHOW_CORRECT_LABEL"]
        else:
            worked["options"] = [
                {"id": distractor, "display_kind": "label", "display_value": distractor},
                {"id": target, "display_kind": "label", "display_value": target},
            ]
            worked["correct_option_id"] = target
            worked["action_sequence"] = ["SHOW_IMAGE", "SHOW_TWO_LABEL_OPTIONS", "SHOW_CORRECT_OPTION"]
        worked_items.append(worked)
    return {
        "id": block["id"],
        "teacher_text": "MODEL_TURNS",
        "expected_answers": [],
        "invariants": [
            *block["teaching_claims"],
            "This worked local model is emitted immediately before its bound controlled gate.",
            "Every displayed object is an exact pixel-reviewed image-bank photograph; no picture-book illustration is used.",
        ],
        "asset_ids": assets,
        "target_language_required": False,
        "response_mode": "model_only",
        "speaker_identity": None,
        "evidence_use": "presentation_only",
        "teacher_turns": [
            {"speaker": "model", "text": item["label"], "asset_ids": [bank_asset_id(item["label"], 1)]}
            for item in block["items"]
        ],
        "nonverbal_control": {
            "machine_action": f"WORKED_{block['gate']}",
            "spoken_text": None,
            "worked_items": worked_items,
        },
    }


def understanding_check_exercise(block: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    gate_order = ("affirmative", "negative", "W_question", "OR_question")
    target = labels[gate_order.index(block["gate"])]
    target_index = labels.index(target)
    set_start = (target_index // 4) * 4
    distractor = labels[set_start + ((target_index - set_start + 1) % 4)]
    asset_ids = [bank_asset_id(target, 1)]
    if block["gate"] == "affirmative":
        distractor_asset = bank_asset_id(distractor, 1)
        asset_ids.append(distractor_asset)
        options = [
            {"id": f"check-{block['gate']}-{target}", "display_kind": "image", "display_value": None, "asset_id": bank_asset_id(target, 1)},
            {"id": f"check-{block['gate']}-{distractor}", "display_kind": "image", "display_value": None, "asset_id": distractor_asset},
        ]
        answer = options[0]["id"]
        action = "SHOW_LABEL_SELECT_MATCHING_IMAGE"
        semantic_task = "select_image_matching_displayed_bare_label"
        extra_control: dict[str, Any] = {
            "action_sequence": ["SHOW_BARE_LABEL", "SHOW_TWO_IMAGE_OPTIONS", "RECORD_SELECTION"],
        }
        response_mode = "lexical_selection"
    else:
        options = [
            {"id": distractor, "display_kind": "label", "display_value": distractor, "asset_id": None},
            {"id": target, "display_kind": "label", "display_value": target, "asset_id": None},
        ]
        answer = target
        response_mode = "lexical_selection"
        if block["gate"] == "negative":
            action = "SHOW_MISMATCH_SELECT_REPLACEMENT"
            semantic_task = "select_bare_label_replacing_visible_mismatch"
            extra_control = {
                "displayed_mismatch_label": distractor,
                "action_sequence": ["SHOW_FOCUS_IMAGE", "SHOW_VISIBLE_MISMATCH_LABEL", "SHOW_REPLACEMENT_OPTIONS", "RECORD_SELECTION"],
            }
        else:
            action = "SHOW_IMAGE_SELECT_ONE_OF_TWO_LABELS"
            semantic_task = "select_bare_label_matching_displayed_image"
            extra_control = {
                "action_sequence": ["SHOW_IMAGE", "SHOW_TWO_LABEL_OPTIONS", "RECORD_SELECTION"],
            }
    if block["gate"] == "W_question":
        return {
            "id": f"{block['id']}-check-understanding",
            "teacher_text": "MACHINE_CONTROL", "expected_answers": [target],
            "invariants": [
                "Unscored exact-form open bare-label interface check for W_question.",
                "This response confirms the production control only and never contributes to mastery.",
                "Failure replays the worked control once; persistent failure freezes with ALARM.",
            ],
            "asset_ids": [bank_asset_id(target, 1)], "target_language_required": True,
            "response_mode": "bare_label", "speaker_identity": "Ninereeds",
            "evidence_use": "learner_label_and_concept", "scoring_role": "unscored_interface_check",
            "nonverbal_control": control_for_open_label(),
        }
    return {
        "id": f"{block['id']}-check-understanding",
        "teacher_text": "MACHINE_CONTROL",
        "expected_answers": [answer],
        "invariants": [
            f"Unscored interface check for the {block['gate']} machine control.",
            "This response confirms only control understanding and never contributes to label, concept, gate, mixed, or lesson mastery.",
            "Failure replays the worked control once; persistent failure freezes with ALARM rather than entering scored practice.",
        ],
        "asset_ids": asset_ids,
        "target_language_required": False,
        "response_mode": response_mode,
        "speaker_identity": None,
        "evidence_use": "concept_only_nonverbal",
        "scoring_role": "unscored_interface_check",
        "nonverbal_control": {
            "machine_action": action,
            "spoken_text": None,
            "semantic_task": semantic_task,
            "demonstrations": [],
            "options": options,
            **extra_control,
        },
    }


def make_assets(selection: dict[str, Any], imagegen: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assets: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    derived_masters = selection.get("derived_masters")
    if not isinstance(derived_masters, list):
        single_master = selection.get("derived_master")
        derived_masters = [single_master] if isinstance(single_master, dict) else []
    for derived_master in derived_masters:
        master_id = derived_master["id"]
        assets.append({
            "id": master_id, "purpose": derived_master["purpose"], "status": "reviewed_usable",
            "source": "imagegen_generate", "path": derived_master["path"], "sha256": derived_master["sha256"],
            "review_receipt_id": None, "parent_asset_id": None, "crop_xywh": None,
            "canonical_reference_ids": [f"image-bank-kind:{label}" for label in selection["assets_by_label"]],
            "attempted_sources": ["registry_exact_pixel_review", "built_in_image_gen"],
            "escalation_reason": "Registry candidates repeatedly introduced competing frontier objects, neighboring utensil bleed, or learner-facing text.",
        })
        claim = derived_master["teaching_claim"]
        operations.append({
            "id": f"op-{master_id}", "type": "imagegen_generate", "status": "accepted",
            "teaching_claims": [claim], "parent_asset_id": None, "output_asset_id": master_id,
            "prompt": derived_master["prompt"], "attempts": [derived_master["attempt_id"]], "crop_xywh": None,
            "receipt_path": None, "receipt_sha256": None,
            "verification": {"reviewer_role": "human", "decision": "accepted", "claim_results": [{"claim": claim, "passed": True, "evidence": derived_master["pixel_review"]}], "rejection_reasons": [], "receipt_path": None, "receipt_sha256": None},
        })
    for label, selected in selection["assets_by_label"].items():
        for ordinal, source in enumerate(selected, 1):
            asset_id = bank_asset_id(label, ordinal)
            generated_panel = source.get("source_kind") == "generated_panel"
            filename = f"{label}-{ordinal:02d}-oi-{source['asset_id']}.jpg"
            path = Path(source["lesson_path"]) if generated_panel else Path("training_data/grounded_stories/assets/lessons/L001/image_bank") / filename
            assets.append({
                "id": asset_id,
                "purpose": f"reviewed image-bank depiction of {label}; variant {ordinal}",
                "status": "reviewed_usable",
                "source": "deterministic_crop" if generated_panel else "registry",
                "path": str(path),
                "sha256": source["sha256"],
                "review_receipt_id": None,
                "parent_asset_id": source.get("parent_asset_id") if generated_panel else None,
                "crop_xywh": source.get("crop_xywh") if generated_panel else None,
                "canonical_reference_ids": [f"image-bank-kind:{label}"],
                "attempted_sources": ["built_in_image_gen", source["source_id"]] if generated_panel else ["open_images_v7", source["source_id"]],
                "escalation_reason": source.get("escalation_reason") if generated_panel else None,
            })
            claim = source["crop_necessity"] if generated_panel else f"Full-frame photograph is an unambiguous reviewed depiction of {label}; no crop is needed."
            operations.append({
                "id": f"op-{asset_id}", "type": "literal_crop" if generated_panel else "reuse", "status": "accepted",
                "teaching_claims": [claim], "parent_asset_id": source.get("parent_asset_id") if generated_panel else None, "output_asset_id": asset_id,
                "prompt": None, "attempts": [] if generated_panel else [f"registry-asset-{source['asset_id']}"], "crop_xywh": source.get("crop_xywh") if generated_panel else None,
                "receipt_path": None, "receipt_sha256": None,
                "verification": {"reviewer_role": "human", "decision": "accepted", "claim_results": [{"claim": claim, "passed": True, "evidence": source["pixel_review"]}], "rejection_reasons": [], "receipt_path": None, "receipt_sha256": None},
            })

    if imagegen.get("operation") == "deterministic_compose":
        for page_number, page in enumerate(imagegen["pages"], 1):
            asset_id = story_asset_id(page_number)
            assets.append({
                "id": asset_id, "purpose": f"picture-book page {page_number}", "status": "reviewed_usable",
                # The compositor is upstream production provenance. At lesson
                # assembly time these already-rendered, pixel-reviewed bytes are
                # reused unchanged under the methodology's licensed vocabulary.
                "source": "reuse", "path": page["path"], "sha256": page["sha256"],
                "review_receipt_id": None, "parent_asset_id": None, "crop_xywh": None,
                "canonical_reference_ids": [f"image-bank-kind:{label}" for label in selection["assets_by_label"]],
                "attempted_sources": ["immutable_reviewed_cards", "deterministic_picture_card_compositor"], "escalation_reason": None,
            })
            claim = page["teaching_claim"]
            operations.append({
                "id": f"op-{asset_id}", "type": "reuse", "status": "accepted",
                "teaching_claims": [claim], "parent_asset_id": None, "output_asset_id": asset_id,
                "prompt": None, "attempts": ["reviewed_deterministic_picture_card_composition"], "crop_xywh": None,
                "receipt_path": None, "receipt_sha256": None,
                "verification": {"reviewer_role": "human", "decision": "accepted", "claim_results": [{"claim": claim, "passed": True, "evidence": page["pixel_review"]}], "rejection_reasons": [], "receipt_path": None, "receipt_sha256": None},
            })
        return assets, operations

    masters = imagegen.get("masters")
    if not isinstance(masters, list):
        masters = [{"id": "storyboard-master", **imagegen["master"], "purpose": "purpose-made picture-book storyboard master", "teaching_claim": "The storyboard master preserves the frozen story objects through one coherent event.", "prompt": imagegen["prompt"]}]
    for master in masters:
        master_id = master["id"]
        assets.append({
            "id": master_id, "purpose": master["purpose"],
            "status": "reviewed_usable", "source": "imagegen_generate", "path": master["path"],
            "sha256": master["sha256"], "review_receipt_id": None, "parent_asset_id": None,
            "crop_xywh": None,
            "canonical_reference_ids": [f"image-bank-kind:{label}" for label in selection["assets_by_label"]],
            "attempted_sources": ["built_in_image_gen"], "escalation_reason": None,
        })
        master_claim = master["teaching_claim"]
        operations.append({
            "id": f"op-{master_id}", "type": "imagegen_generate", "status": "accepted",
            "teaching_claims": [master_claim], "parent_asset_id": None, "output_asset_id": master_id,
            "prompt": master["prompt"], "attempts": [master.get("attempt_id", "built-in-imagegen-v1")], "crop_xywh": None,
            "receipt_path": None, "receipt_sha256": None,
            "verification": {"reviewer_role": "human", "decision": "accepted", "claim_results": [{"claim": master_claim, "passed": True, "evidence": master["pixel_review"]}], "rejection_reasons": [], "receipt_path": None, "receipt_sha256": None},
        })
    for page_number, page in enumerate(imagegen["panel_extraction"]["pages"], 1):
        asset_id = story_asset_id(page_number)
        x0, y0, x1, y1 = page["xyxy"]
        crop = [x0, y0, x1 - x0, y1 - y0]
        parent_master_id = page.get("parent_master_id", masters[0]["id"])
        assets.append({
            "id": asset_id, "purpose": f"picture-book page {page_number}", "status": "reviewed_usable",
            "source": "deterministic_crop", "path": page["path"], "sha256": page["sha256"],
            "review_receipt_id": None, "parent_asset_id": parent_master_id, "crop_xywh": crop,
            "canonical_reference_ids": [f"image-bank-kind:{label}" for label in selection["assets_by_label"]],
            "attempted_sources": ["intentional_storyboard_panel_extraction"], "escalation_reason": None,
        })
        claim = f"Page {page_number} preserves the complete intended storyboard panel without removing any teaching operand."
        operations.append({
            "id": f"op-{asset_id}", "type": "literal_crop", "status": "accepted",
            "teaching_claims": [claim], "parent_asset_id": parent_master_id, "output_asset_id": asset_id,
            "prompt": None, "attempts": [], "crop_xywh": crop,
            "receipt_path": None, "receipt_sha256": None,
            "verification": {"reviewer_role": "human", "decision": "accepted", "claim_results": [{"claim": claim, "passed": True, "evidence": "The crop follows a deliberate panel border; the full scene remains visible."}], "rejection_reasons": [], "receipt_path": None, "receipt_sha256": None},
        })
    return assets, operations


def make_story_pages(stage_pages: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    pages: list[dict[str, Any]] = []
    page_assets: dict[str, str] = {}
    for index, page in enumerate(stage_pages["pages"], 1):
        asset_id = story_asset_id(index)
        page_assets[page["id"]] = asset_id
        turns = page["dialogue_turns"]
        pages.append({
            "id": page["id"], "asset_id": asset_id,
            "caption": " · ".join(turn["text"] for turn in turns),
            "scene_facts": list(page["scene_facts"]),
            "dialogue_turns": [
                {"id": turn["id"], "speaker": turn["speaker"], "text": turn["text"], "asset_ids": [asset_id], "responds_to": turn["responds_to"]}
                for turn in turns
            ],
        })
    return pages, page_assets


def story_check(check: dict[str, Any], page_assets: dict[str, str]) -> dict[str, Any]:
    anchor_asset = page_assets[check["anchor_page_id"]]
    if check["control"]["machine_action"] in {"SHOW_PAGE_SELECT_NEXT_SCENE", "SHOW_PAGE_SELECT_PREVIOUS_SCENE"}:
        options = [
            {"id": option["id"], "asset_id": page_assets[option["page_id"]], "visual_entity": page_assets[option["page_id"]]}
            for option in check["options"]
        ]
        asset_ids = [anchor_asset, *(option["asset_id"] for option in options)]
        return {
            "id": check["id"], "teacher_text": "MACHINE_CONTROL",
            "expected_answers": list(check["expected_option_ids"]),
            "invariants": [check["story_fact"], check["evidentiary_limit"]],
            "asset_ids": asset_ids, "target_language_required": False,
            "response_mode": "story_sequence_selection", "speaker_identity": None,
            "evidence_use": "concept_only_nonverbal",
            "nonverbal_control": {
                "machine_action": check["control"]["machine_action"], "spoken_text": None,
                "semantic_task": check["control"]["semantic_task"], "anchor_asset_id": anchor_asset,
                "demonstrations": [], "options": options,
            },
        }
    options = [
        {"id": label, "display_kind": "label", "display_value": label, "asset_id": None}
        for label in check["control"]["option_labels"]
    ]
    return {
        "id": check["id"], "teacher_text": "MACHINE_CONTROL",
        "expected_answers": list(check["expected_answers"]),
        "invariants": [check["story_fact"], check["evidentiary_limit"]],
        "asset_ids": [anchor_asset], "target_language_required": False,
        "response_mode": "lexical_selection", "speaker_identity": None,
        "evidence_use": "concept_only_nonverbal",
        "nonverbal_control": {
            "machine_action": check["control"]["machine_action"], "spoken_text": None,
            "semantic_task": check["control"]["semantic_task"], "anchor_asset_id": anchor_asset,
            "demonstrations": [], "options": options,
        },
    }


def direct_application(check: dict[str, Any], ordinal: int) -> dict[str, Any]:
    target = check["target_label"]
    return {
        "id": check["id"], "teacher_text": "MACHINE_CONTROL",
        "expected_answers": list(check["expected_answers"]),
        "invariants": [check["not_narrative_evidence_reason"], "The depiction was not used in the local presentation model."],
        "asset_ids": [bank_asset_id(target, ordinal)], "target_language_required": True,
        "response_mode": "bare_label", "speaker_identity": "Ninereeds",
        "evidence_use": "learner_label_and_concept", "nonverbal_control": control_for_open_label(),
    }


def make_reserves(language: dict[str, Any], labels: list[str]) -> list[dict[str, Any]]:
    reserves: list[dict[str, Any]] = []
    for item in language["interventions"]["train_more"]["reserve_exercises"]:
        stage = {key: value for key, value in item.items() if key != "reserve_for"}
        reserves.append(final_exercise(stage, 5, labels))
    return reserves


def make_present_again_retests(
    language: dict[str, Any], labels: list[str]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """Create one fresh, unscored parallel retest per controlled base item."""
    presentation_by_gate = {block["gate"]: block["id"] for block in language["presentation"]}
    retests: list[dict[str, Any]] = []
    dispatch: dict[str, dict[str, str]] = {}
    for gate in ("affirmative", "negative", "W_question", "OR_question"):
        for item in language["controlled_practice"][gate]:
            retest = final_exercise(item, 4, labels)
            retest["id"] = f"{item['id']}-cold-retest"
            retest["scoring_role"] = "unscored_parallel_retest"
            retest["invariants"].append(
                "This fresh-photo diagnostic never contributes to mastery or replaces the original base score."
            )
            retests.append(retest)
            dispatch[item["id"]] = {
                "gate": gate,
                "target_label": item["target_label"],
                "presentation_id": presentation_by_gate[gate],
                "worked_item_label": item["target_label"],
                "cold_retest_exercise_id": retest["id"],
            }
    return retests, dispatch


def story_interface_tutorial(page_assets: dict[str, str], labels: list[str]) -> list[dict[str, Any]]:
    """Teach and check next-scene selection before scored story questions."""
    page_ids = list(page_assets)
    page_02 = page_assets[page_ids[1]]
    page_03 = page_assets[page_ids[2]]
    page_04 = page_assets[page_ids[3]]
    page_07 = page_assets[page_ids[6]]
    page_08 = page_assets[page_ids[7]]
    model = {
        "id": "l001-story-interface-model", "teacher_text": "MODEL_TURNS",
        "expected_answers": [],
        "invariants": [
            "This worked example teaches selection of the scene that comes next in the completed story.",
            "The page-02 anchor visibly advances to page 03; the nonadjacent page 07 is the distractor.",
        ],
        "asset_ids": [page_02, page_03, page_07], "target_language_required": False,
        "response_mode": "model_only", "speaker_identity": None,
        "evidence_use": "presentation_only",
        "teacher_turns": [{"speaker": "model", "text": "plate", "asset_ids": [page_02, page_03]}],
        "nonverbal_control": {
            "machine_action": "WORKED_STORY_NEXT_SCENE", "spoken_text": None,
            "worked_items": [{
                "anchor_asset_id": page_02, "option_asset_ids": [page_03, page_07], "correct_option_asset_id": page_03,
                "action_sequence": ["SHOW_ANCHOR_PAGE", "SHOW_TWO_SCENE_OPTIONS", "SHOW_CORRECT_OPTION"],
            }],
        },
    }
    check = {
        "id": "l001-story-interface-check-understanding", "teacher_text": "MACHINE_CONTROL",
        "expected_answers": ["story-check-next-page-04"],
        "invariants": [
            "This unscored check confirms selection of the next scene after page 03.",
            "Failure replays the interface model once; persistent failure sounds ALARM and freezes.",
        ],
        "asset_ids": [page_03, page_04, page_08], "target_language_required": False,
        "response_mode": "story_sequence_selection", "speaker_identity": None,
        "evidence_use": "concept_only_nonverbal", "scoring_role": "unscored_interface_check",
        "nonverbal_control": {
            "machine_action": "SHOW_PAGE_SELECT_NEXT_SCENE", "spoken_text": None,
            "semantic_task": "select_scene_of_next_story_page", "anchor_asset_id": page_03,
            "demonstrations": [],
            "options": [
                {"id": "story-check-next-page-04", "asset_id": page_04, "visual_entity": page_04},
                {"id": "story-check-distractor-page-08", "asset_id": page_08, "visual_entity": page_08},
            ],
        },
    }
    return [model, check]


def assemble(args: argparse.Namespace) -> dict[str, Any]:
    selection = load(args.selection)
    thesis = load(args.thesis)
    language = load(args.language)
    kernel = load(args.kernel)
    stage_pages = load(args.pages)
    comprehension = load(args.comprehension)
    bank_selection = load(args.image_bank)
    imagegen = load(args.imagegen_receipt)
    runtime_contract = load(args.runtime_contract)
    labels = list(language["frontier_labels"])

    assets, operations = make_assets(bank_selection, imagegen)
    presentation: list[dict[str, Any]] = []
    presentation_bindings: dict[str, list[str]] = {}
    presentation_model_ids: list[str] = []
    for block in language["presentation"]:
        model = model_exercise(block, labels)
        check = understanding_check_exercise(block, labels)
        presentation.extend((model, check))
        presentation_model_ids.append(model["id"])
        presentation_bindings[block["gate"]] = [model["id"], check["id"]]
    controlled = {
        gate: [final_exercise(item, 2, labels) for item in language["controlled_practice"][gate]]
        for gate in ("affirmative", "negative", "W_question", "OR_question")
    }
    label_mixed_counts = {label: 0 for label in labels}
    mixed = []
    for item in language["mixed_practice"]["ordered_exercises"]:
        label = item["target_label"]
        ordinal = 2
        label_mixed_counts[label] += 1
        mixed.append(final_exercise(item, ordinal, labels))
    recap = [final_exercise(item, 2, labels) for item in language["recap"]]
    story_pages, page_assets = make_story_pages(stage_pages)
    book_checks = story_interface_tutorial(page_assets, labels)
    book_checks.extend(story_check(check, page_assets) for check in comprehension["narrative_comprehension_checks"])
    book_checks.extend(direct_application(check, 3) for check in comprehension["direct_application_checks"])
    reserves = make_reserves(language, labels)
    present_again_retests, present_again_dispatch = make_present_again_retests(language, labels)

    phase_sequence: list[dict[str, Any]] = []
    for gate in ("affirmative", "negative", "W_question", "OR_question"):
        phase_sequence.append({"phase": "presentation", "exercise_ids": presentation_bindings[gate]})
        phase_sequence.append({"phase": gate, "exercise_ids": [item["id"] for item in controlled[gate]]})
    story_comprehension_ids = [
        item["id"] for item in book_checks
        if item.get("evidence_use") != "learner_label_and_concept"
    ]
    story_transfer_ids = [
        item["id"] for item in book_checks
        if item.get("evidence_use") == "learner_label_and_concept"
    ]
    phase_sequence.extend([
        {"phase": "mixed_practice", "exercise_ids": [item["id"] for item in mixed]},
        {"phase": "picture_book", "exercise_ids": [item["id"] for item in story_pages]},
        {"phase": "comprehension", "exercise_ids": story_comprehension_ids},
        {"phase": "transfer", "exercise_ids": story_transfer_ids},
        {"phase": "closing_recap", "exercise_ids": [item["id"] for item in recap]},
    ])

    policy_paths = {
        "learner_state": REPO_ROOT / "output/lessons/L000-handhold-attempt-001/inputs/learner-state.json",
        "known_closure": REPO_ROOT / "output/lessons/L000-handhold-attempt-001/inputs/known-closure.json",
        "teaching_methodology": REPO_ROOT / "mission_hub/wiki/teaching.md",
        "world_bible": REPO_ROOT / "training_data/grounded_stories/world_bible.md",
        "identity_policy": REPO_ROOT / "docs/ninereeds_identity_and_lesson_policy.md",
        "instructor_qualification": REPO_ROOT / "mission_hub/research/instructor-qualification-policy.json",
        "instructor_qualification_state": REPO_ROOT / "mission_hub/research/instructor-qualification-state.json",
        "lesson_format": REPO_ROOT / "mission_hub/research/full-lesson-format-policy.json",
        "lesson_pattern": REPO_ROOT / "mission_hub/research/lesson-pattern-picture-card-lexical-bootstrap-v1.json",
        "material_scope": args.thesis.parents[2] / "inputs/material-scope-decision.json",
        "curriculum": REPO_ROOT / "docs/curriculum_v6_sol/curriculum_v6.json",
    }
    sources = [binding(role, path) for role, path in policy_paths.items()]
    sources.extend([
        binding("selection_packet", args.selection), binding("lesson_thesis", args.thesis),
        binding("language_stage", args.language), binding("story_kernel", args.kernel),
        binding("story_pages", args.pages), binding("story_comprehension", args.comprehension),
        binding("image_bank_selection", args.image_bank), binding("picture_book_imagegen", args.imagegen_receipt),
        binding("runtime_contract", args.runtime_contract),
    ])
    selected = selection["selected_entry"]
    selection_packet_rel = rel(args.selection)
    attempt_root = args.thesis.parents[2]
    authoring_prompt = attempt_root / "stages/06-assembly/task-card-luna-phased-005.json"
    authoring_receipt = attempt_root / "stages/06-assembly/luna-phased-authoring-receipt-005.json"
    reserve_ids = [item["id"] for item in reserves]
    reserve_gate_by_id = {
        item["id"]: item["reserve_for"]
        for item in language["interventions"]["train_more"]["reserve_exercises"]
    }
    reserve_ids_by_gate = {
        gate: [item["id"] for item in reserves if reserve_gate_by_id[item["id"]] == gate]
        for gate in ("affirmative", "negative", "W_question", "OR_question")
    }
    mixed_ids = [item["id"] for item in mixed]
    presentation_ids = presentation_model_ids

    lesson = {
        "schema_version": "ninereeds_lesson_contract_v3",
        "assembly": {"mode": "handhold", "selection_packet_path": selection_packet_rel, "selection_packet_sha256": sha(args.selection), "conducted_entry_id": "L001", "conducted_sequence_number": 2},
        "authoring": {"actor": "luna", "prompt_path": rel(authoring_prompt), "prompt_sha256": sha(authoring_prompt), "receipt_path": rel(authoring_receipt), "receipt_sha256": sha(authoring_receipt)},
        "independent_review": {"required": True, "reviewer_role": "sol", "decision": "pending", "rubric_id": "sol-lesson-assembly-review-v1", "receipt_path": None, "receipt_sha256": None, "findings": []},
        "visual_plan": {"lesson_asset_root": "training_data/grounded_stories/assets/lessons/L001", "flux_max_attempts": 3, "operations": operations},
        "lesson_id": "lesson-ordinary-table-objects-v2", "status": "draft", "variant": "picture_book", "target_language": "English", "topic": "Ordinary table objects",
        "point": {"id": "L001-table-object-labels", "claim": f"Activate the labels {', '.join(labels)}", "novelty_kind": "lexical_set"},
        "vocabulary_plan": {"selection_basis": "point_coherence_stage_and_budget", "default_tested_item_count": 16, "selected_tested_item_count": len(labels), "set_size": 4, "sets": [{"id": item["set_id"], "item_ids": item["items"]} for item in thesis["material_count"]["sets"]], "rationale": thesis["material_count"]["rationale"], "structural_exception": thesis["material_count"]["structural_exception"]},
        "selection": {"learner_state_artifact_id": selection["learner_evidence"]["learner_state_artifact_id"], "known_closure_artifact_id": selection["learner_evidence"]["known_closure_artifact_id"], "rationale": "L001 is prepared prospectively while actual learner closure remains empty; compiled L000 is a readiness receipt, not learner evidence.", "predicted_dosage": f"Four local models, four {len(labels)}-item controlled gates, {len(mixed)} mixed items, {len(story_pages)} story pages, {len(book_checks)} comprehension and transfer checks, and {len(recap)} closing retrievals."},
        "prerequisites": [],
        "source_bindings": sources,
        "world": {"recurring_entities": [], "new_entries": [], "extras_policy": "unnamed_nonrecurring_no_persistent_history"},
        "language_boundary": {"permitted_rescue_languages": [], "correct_meaning_wrong_language": "concept_may_be_understood_target_production_not_demonstrated", "off_topic_response": "ALARM_FREEZE; preserve the log and do not improvise learner-facing language.", "role_diversion_response": "ALARM_FREEZE; preserve the Instructor role and emit no further learner-facing language."},
        "phases": {"presentation": presentation, "presentation_bindings": presentation_bindings, "execution_sequence": phase_sequence, "controlled_practice": controlled, "mixed_practice": mixed, "transfer": recap},
        "picture_book": {
            "instructional_kernel": f"{kernel['initial_state_or_goal']} {kernel['meaningful_development']} {kernel['resolution_or_stopping_state']}",
            "story_arc": {"initial_state_or_goal": kernel["initial_state_or_goal"], "meaningful_development": kernel["meaningful_development"], "resolution_or_stopping_state": kernel["resolution_or_stopping_state"], "continuity_bindings": [f"{item['entity']}={item['canonical_reference_id']}" for item in kernel["continuity_bindings"]], "coherence_test": "Every page advances one continuous eight-card organizing event; the final orderly board and helper celebration visibly resolve the initial disorder without asserting object-specific matching positions."},
            "world_grounding": {"selected_world_objective": kernel["world_grounding"]["selected_world_objective"], "scored_world_claims": kernel["world_grounding"]["scored_story_claims"], "visual_safety_metadata": [f"{item['entity']}: {item['constraint']}" for item in kernel["world_grounding"]["visual_safety_metadata"]], "forbidden_novelties": kernel["world_grounding"]["forbidden_novelties"]},
            "identity_safety": stage_pages["identity_safety"], "pages": story_pages, "comprehension": book_checks,
        },
        "assets": assets,
        "adaptive": {
            "presentation_replay_after_failures": 1, "maximum_teacher_turns": runtime_contract["budgets"]["teacher_cap"], "mixed_practice_cap": len(mixed),
            "runtime_contract": runtime_contract,
            "controller_actions": ["CONTINUE", "PRESENT_AGAIN", "TRAIN_MORE", "TRAIN_LONGER", "REPLAY_LESSON", "ALARM", "FINISH"],
            "marker_intervention": {"action": "USE_MARKERS", "enabled": False, "role_delimiters": {"subject": ["(", ")"], "predicate": ["*", "*"], "recipient": ["[", "]"], "object": ["{", "}"], "possessor": ["<", ">"]}, "focus_delimiter": ["+", "+"], "levels": ["none", "constituent_only", "full_role_map", "frontier_focus"], "scheduled_presentation_fraction": 0.0, "immediate_retest": "unmarked", "expected_student_output": "unmarked", "fade_after_consecutive_unmarked_successes": 3, "fade_after_distinct_scenes": 2, "max_scored_mixed_prompts": len(mixed), "max_unchanged_failure_episodes": 2, "terminal_outcome": "defer_and_revisit"},
            "present_again": {"action": "PRESENT_AGAIN", "source": "frozen_presentation_ids_only", "presentation_ids": presentation_ids, "dispatch_table": present_again_dispatch, "retest_exercises": present_again_retests, "release_rule": "after_each_incorrect_controlled_base_item_dispatch_its_exact_worked_item_once_then_its_fresh_unscored_cold_retest_if_target_and_global_use_budget_remain", "maximum_total_uses": len(labels), "return_rule": "after_the_mapped_fresh_unscored_cold_retest_resume_the_next_not_yet_scored_frozen_base_item_without_changing_the_original_score", "exhaustion": "defer_and_revisit"},
            "train_more": {"action": "TRAIN_MORE", "source": "preauthored_reserve_only", "reserve_ids": reserve_ids, "reserve_exercises": reserves, "release_rule": f"after_a_gate_records_fewer_than_{math.ceil(0.75 * len(labels))}_of_{len(labels)}_base_correct_release_exactly_one_v5_reserve_for_each_incorrect_base_label_in_frozen_base_order_and_pass_only_if_every_released_reserve_is_correct", "selection_rule": "failed_labels_only_once_each_in_frozen_base_order", "score_rule": "reserve_score_is_separate_from_base_score_with_denominator_equal_to_released_failed_labels", "max_items_per_gate": max(len(ids) for ids in reserve_ids_by_gate.values()), "exhaustion": "defer_and_revisit", "gate_execution": {
                gate: {
                    "base_exercise_ids": [item["id"] for item in controlled[gate]],
                    "base_pass_minimum_correct": math.ceil(0.75 * len(controlled[gate])),
                    "base_denominator": len(controlled[gate]),
                    "reserve_exercise_ids": reserve_ids_by_gate[gate],
                    "reserve_release_trigger": f"base_correct_below_{math.ceil(0.75 * len(controlled[gate]))}_then_filter_to_incorrect_base_labels",
                    "post_reserve_pass_rule": "all_released_reserves_correct",
                    "terminal_on_pass": "continue",
                    "terminal_on_reserve_failure_or_exhaustion": "defer_and_revisit",
                    "terminal_on_alarm": "freeze",
                }
                for gate in ("affirmative", "negative", "W_question", "OR_question")
            }},
            "train_longer": {"action": "TRAIN_LONGER", "source": "frozen_ids_only", "eligible_item_ids": language["interventions"]["train_longer"]["additional_ordered_exercise_ids"], "ordered_item_ids": language["interventions"]["train_longer"]["additional_ordered_exercise_ids"], "extension_event_ids": [f"l001-tl-v2-{index:02d}" for index in range(1, 9)], "extension_source_map": {f"l001-tl-v2-{index:02d}": source_id for index, source_id in enumerate(language["interventions"]["train_longer"]["additional_ordered_exercise_ids"], 1)}, "identity_rule": "Each extension event has a distinct event ID while reusing exactly one frozen source exercise contract; extension scores never alter the 32-item base denominator.", "ordering_rule": "Use only the frozen order after the base mixed block; never release TRAIN_MORE reserves here.", "max_additional_items": 8, "no_immediate_duplicate": True, "denominator": 8, "minimum_successes": 7, "release_predicate": "initial_mixed_terminal_and_mixed_successes_below_26_of_32_and_no_alarm_and_no_prior_train_longer_release", "terminal_on_success": "mark_mixed_remediated_then_continue_to_picture_book", "terminal_on_failure": "defer_and_revisit", "stop_rule": language["interventions"]["train_longer"]["stop_rule"], "exhaustion": "defer_and_revisit"},
            "mixed_execution": {"ordered_item_ids": mixed_ids, "denominator": len(mixed_ids), "minimum_successes": math.ceil(0.8 * len(mixed_ids)), "maximum_items": len(mixed_ids), "stop_rule": f"Run all {len(mixed_ids)} frozen mixed items once, then evaluate {math.ceil(0.8 * len(mixed_ids))}-of-{len(mixed_ids)} before any TRAIN_LONGER release."},
            "replay_lesson": {"action": "REPLAY_LESSON", "release_rule": "At most once after a complete non-alarm execution fails aggregate mastery.", "maximum_replays": 1, "stop_rule": "After one full replay, finish if mastery passes; otherwise defer and revisit.", "exhaustion": "defer_and_revisit"},
            "finish": {"action": "FINISH", "eligibility": f"All four controlled gates pass directly or through failed-label TRAIN_MORE remediation; mixed either reaches {math.ceil(0.8 * len(mixed_ids))} of {len(mixed_ids)} base or records a separate TRAIN_LONGER success at 7 of 8; every story page is emitted; all six story-sequence checks and eight unseen transfer checks are recorded; and closing_recap reaches {math.ceil(0.75 * len(recap))} of {len(recap)}.", "behavior": "close_lesson_write_report_no_further_prompts"},
            "controller_transition_table": {
                "any_non_frozen_state+ALARM": "frozen_no_further_teacher_turns_preserve_log",
                "presentation_check_pass+CONTINUE": "bound_controlled_gate",
                "controlled_base_incorrect+PRESENT_AGAIN": "mapped_worked_item_then_fresh_unscored_retest_then_next_base_item",
                "controlled_gate_pass+CONTINUE": "next_local_presentation",
                "controlled_gate_fail+TRAIN_MORE": "release_exactly_failed_labels_v5_reserves_in_base_order_then_next_local_presentation_or_defer",
                "mixed_pass+CONTINUE": "picture_book",
                "mixed_fail+TRAIN_LONGER": "release_exactly_eight_distinct_extension_events_then_picture_book_on_7_of_8_or_defer",
                "picture_book_complete+CONTINUE": "story_interface_then_comprehension",
                "comprehension_complete+CONTINUE": "unseen_transfer",
                "transfer_complete+CONTINUE": "closing_recap",
                "epoch1_closing_recap_terminal": "finish_if_aggregate_mastery_true_else_one_base_only_replay_if_full_preflight_passes_else_defer",
                "epoch2_any_adaptive_action": "forbidden",
                "epoch2_closing_recap_terminal": "finish_if_epoch2_aggregate_mastery_true_else_defer_no_second_replay",
                "all_terminal_conditions_pass+FINISH": "close_and_write_report",
                "frozen+any_action": "forbidden",
            },
            "alarm": {"action": "ALARM", "triggers": [*language["interventions"]["alarm_conditions"], "Any story page is missing, out of order, visually contradictory, or paired with the wrong caption.", "Any story-interface worked example or scored answer does not match the centered active card.", "Any asset hash, exact pixel review, or required control is unavailable."], "behavior": "freeze_immediately_preserve_log_no_further_teacher_turns"},
        },
        "rehearsal": {"pattern_id": "picture-book-lexical-bootstrap-v1", "decision": "required_pending", "reason": "New early lexical-control pattern requires static Sol approval and a full handhold rehearsal before freeze.", "qualification_record_path": rel(policy_paths["instructor_qualification_state"]), "qualification_record_sha256": sha(policy_paths["instructor_qualification_state"]), "evidence_artifact_ids": []},
    }
    return lesson


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--thesis", type=Path, required=True)
    parser.add_argument("--language", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--comprehension", type=Path, required=True)
    parser.add_argument("--image-bank", type=Path, required=True)
    parser.add_argument("--imagegen-receipt", type=Path, required=True)
    parser.add_argument("--runtime-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    lesson = assemble(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(lesson, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"assembled lexical lesson: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
