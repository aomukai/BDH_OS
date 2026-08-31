#!/usr/bin/env python3
"""Read-only causal audit of the terminal unfiltered Campaign 36B anatomy."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch

from amorphous.selection import CohortAdmissionEvidence, selective_admission_decision
from amorphous.student import build_amorphous_student
from cortex.siglip2 import BoundedVisualResampler, Siglip2ProjectorConfig
from meta.scripts.train_campaign36b_bootstrap import (
    BOOTSTRAP_MANIFEST_IDENTITY,
    atomic_json,
    load_features,
    resolve_source,
    sha256,
    visual_objective,
)


AUDIT_SCHEMA = "ninereeds_campaign36b_terminal_anatomy_audit_v1"


def rank(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def event_identity(session_id: str, offset: int, event: dict[str, Any]) -> str:
    return (
        f"{BOOTSTRAP_MANIFEST_IDENTITY}|{session_id}|{offset}|"
        f"{event['ordinal']}|{event['asset_sha256']}"
    )


def select_panels(manifest: dict[str, Any], root: Path) -> tuple[list[dict], list[dict]]:
    all_events: list[dict[str, Any]] = []
    by_ordinal: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for session_index, session in enumerate(manifest["sessions"]):
        events_path = resolve_source(session["events_path"], root)
        if sha256(events_path) != session["events_sha256"]:
            raise ValueError(f"event bytes changed for {session['session_id']}")
        events = json.loads(events_path.read_text(encoding="utf-8"))
        for offset, event in enumerate(events):
            identity = event_identity(session["session_id"], offset, event)
            record = {
                **event,
                "identity": identity,
                "rank": rank("audit-v1|" + identity),
                "session_id": session["session_id"],
                "session_index": session_index,
                "event_offset": offset,
                "feature_path": session["feature_path"],
                "feature_sha256": session["feature_sha256"],
                "feature_bytes": session["feature_bytes"],
            }
            all_events.append(record)
            by_ordinal[int(event["ordinal"])].append(record)
    audit = sorted(all_events, key=lambda item: item["rank"])[:256]
    anchors = [
        min(
            by_ordinal[ordinal],
            key=lambda item: rank("anchor-v1|" + item["identity"]),
        )
        for ordinal in sorted(by_ordinal)[:64]
    ]
    return audit, anchors


def materialize_features(
    records: list[dict[str, Any]], manifest_root: Path,
) -> dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    wanted_by_session: dict[int, set[str]] = defaultdict(set)
    representative: dict[int, dict[str, Any]] = {}
    for record in records:
        wanted_by_session[record["session_index"]].add(record["asset_sha256"])
        representative[record["session_index"]] = record
    selected: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    for session_index in sorted(wanted_by_session):
        record = representative[session_index]
        path = resolve_source(record["feature_path"], manifest_root)
        if path.stat().st_size != record["feature_bytes"] or sha256(path) != record["feature_sha256"]:
            raise ValueError(f"feature bytes changed for session {session_index}")
        archive = load_features(path)
        for digest in wanted_by_session[session_index]:
            if digest not in archive:
                raise ValueError(f"selected feature is absent: {digest}")
            selected[digest] = archive[digest]
    return selected


@torch.no_grad()
def evaluate_panel(student, resampler, records, features) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for record in records:
        loss, evidence = visual_objective(
            student,
            resampler,
            features[record["asset_sha256"]],
            record["completion"],
        )
        values[record["identity"]] = {
            "nll": float(loss.cpu()),
            "exact": bool(evidence["target_token_exact"]),
        }
    return values


def compare(enabled, ablated) -> dict[str, Any]:
    identities = sorted(enabled)
    deltas = [ablated[key]["nll"] - enabled[key]["nll"] for key in identities]
    return {
        "count": len(deltas),
        "mean_delta_nll": statistics.fmean(deltas),
        "median_delta_nll": statistics.median(deltas),
        "helpful_fraction": sum(value > 0 for value in deltas) / len(deltas),
        "exact_lost_when_ablated": sum(
            enabled[key]["exact"] and not ablated[key]["exact"] for key in identities
        ),
        "exact_gained_when_ablated": sum(
            not enabled[key]["exact"] and ablated[key]["exact"] for key in identities
        ),
        "delta_nll": deltas,
    }


def set_disabled(student, indices: list[int]) -> dict[int, str]:
    original = {index: student.substrate.cohorts[index].status for index in indices}
    for index in indices:
        student.substrate.set_cohort_status(index, "dormant")
    return original


def restore_statuses(student, original: dict[int, str]) -> None:
    for index, status in original.items():
        student.substrate.set_cohort_status(index, status)


def birth_groups(report_dir: Path) -> dict[int, list[int]]:
    groups: dict[int, list[int]] = {}
    for path in sorted(report_dir.glob("session-*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        groups[int(report["session_index"])] = sorted(
            int(item["cohort_index"]) for item in report["births"]
        )
    if len(groups) != 31:
        raise ValueError("terminal audit requires all 31 session reports")
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ingress-device", default="cuda:0")
    parser.add_argument("--substrate-device", default="cuda:1")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if (
        manifest.get("input_manifest_sha256") != BOOTSTRAP_MANIFEST_IDENTITY
        or manifest.get("event_count") != 30_220
        or manifest.get("session_count") != 31
    ):
        raise ValueError("audit manifest is not the frozen bootstrap")
    checkpoint_document = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    metadata = checkpoint_document.get("metadata", {})
    if (
        metadata.get("bootstrap_sessions_completed") != 31
        or metadata.get("training_events_consumed") != 30_220
    ):
        raise ValueError("audit checkpoint is not the terminal baseline")

    student, _, _ = build_amorphous_student(
        args.checkpoint,
        frozen_dtype=torch.bfloat16,
        local_files_only=args.local_files_only,
    )
    visual = checkpoint_document["visual_state"]
    resampler = BoundedVisualResampler(Siglip2ProjectorConfig(**visual["config"]))
    resampler.load_state_dict(visual["resampler_state"], strict=True)
    student.place(
        ingress_device=torch.device(args.ingress_device),
        substrate_device=torch.device(args.substrate_device),
        trainable_dtype=torch.bfloat16,
    )
    resampler.to(device=torch.device(args.ingress_device), dtype=torch.bfloat16)
    student.eval(); resampler.eval()

    audit_panel, anchors = select_panels(manifest, args.manifest.parent)
    individual_panel = audit_panel[:32]
    individual_anchors = anchors[:8]
    features = materialize_features(
        [*audit_panel, *anchors], args.manifest.parent
    )
    baseline_audit = evaluate_panel(student, resampler, audit_panel, features)
    baseline_anchors = evaluate_panel(student, resampler, anchors, features)
    groups = birth_groups(args.report_dir)
    result: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA,
        "status": "in_progress",
        "source": {
            "checkpoint": str(args.checkpoint),
            "checkpoint_sha256": sha256(args.checkpoint),
            "bootstrap_manifest_sha256": BOOTSTRAP_MANIFEST_IDENTITY,
        },
        "panels": {
            "audit_identities": [item["identity"] for item in audit_panel],
            "anchor_identities": [item["identity"] for item in anchors],
            "individual_audit_identities": [item["identity"] for item in individual_panel],
            "individual_anchor_identities": [item["identity"] for item in individual_anchors],
        },
        "terminal_anatomy": student.substrate.anatomy(),
        "birth_session_groups": {},
        "sampled_individual_cohorts": {},
        "interpretation_boundary": (
            "terminal ablation estimates later utility; it does not reconstruct "
            "admission-time fitness"
        ),
    }
    atomic_json(args.output, result)

    for session_index, indices in sorted(groups.items()):
        if not indices:
            result["birth_session_groups"][str(session_index)] = {"cohort_indices": []}
            continue
        original = set_disabled(student, indices)
        try:
            ablated_audit = evaluate_panel(student, resampler, audit_panel, features)
            ablated_anchors = evaluate_panel(student, resampler, anchors, features)
        finally:
            restore_statuses(student, original)
        result["birth_session_groups"][str(session_index)] = {
            "cohort_indices": indices,
            "audit": compare(baseline_audit, ablated_audit),
            "anchors": compare(baseline_anchors, ablated_anchors),
        }
        atomic_json(args.output, result)

    newborn_indices = [index for values in groups.values() for index in values]
    sampled = sorted(
        newborn_indices,
        key=lambda index: rank(f"individual-cohort-v1|{index}"),
    )[:128]
    baseline_individual = {item["identity"]: baseline_audit[item["identity"]] for item in individual_panel}
    baseline_individual_anchors = {item["identity"]: baseline_anchors[item["identity"]] for item in individual_anchors}
    for index in sampled:
        original = set_disabled(student, [index])
        try:
            ablated = evaluate_panel(student, resampler, individual_panel, features)
            ablated_anchors = evaluate_panel(student, resampler, individual_anchors, features)
        finally:
            restore_statuses(student, original)
        audit_comparison = compare(baseline_individual, ablated)
        anchor_comparison = compare(baseline_individual_anchors, ablated_anchors)
        proxy_evidence = CohortAdmissionEvidence(
            age_exposures=30_220,
            online_credit_deltas=tuple(audit_comparison["delta_nll"]),
            replay_delta_nll=tuple(audit_comparison["delta_nll"]),
            anchor_harm_nll=tuple(-value for value in anchor_comparison["delta_nll"]),
        )
        birth_session = next(key for key, values in groups.items() if index in values)
        result["sampled_individual_cohorts"][str(index)] = {
            "birth_session": birth_session,
            "cell_ids": list(student.substrate.cohorts[index].cell_ids),
            "audit": audit_comparison,
            "anchors": anchor_comparison,
            "terminal_proxy_admission_decision": selective_admission_decision(proxy_evidence),
        }
        atomic_json(args.output, result)

    decisions = [
        value["terminal_proxy_admission_decision"]
        for value in result["sampled_individual_cohorts"].values()
    ]
    result["terminal_proxy_estimate"] = {
        "sample_size": len(decisions),
        "promote": decisions.count("promote"),
        "provisional": decisions.count("provisional"),
        "dormant": decisions.count("dormant"),
    }
    result["status"] = "complete"
    atomic_json(args.output, result)
    print(json.dumps(result["terminal_proxy_estimate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
