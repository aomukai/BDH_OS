#!/usr/bin/env python3
"""Aggregate every M5 train/evaluate/observer report into a healing record."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_WORKFLOW = "cortex-a815641b-9474-40f1-b6e8-347b5848f554"


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def rounded(value: float | None) -> float | None:
    return round(value, 9) if value is not None and math.isfinite(value) else value


def object_path(root: Path, sha256: str) -> Path:
    return root / "artifacts" / "objects" / sha256[:2] / sha256


def artifact(output: dict[str, Any], kind: str) -> dict[str, Any]:
    matches = [item for item in output.get("artifacts", []) if item.get("kind") == kind]
    if len(matches) != 1:
        raise ValueError(f"expected one {kind} artifact, found {len(matches)}")
    return matches[0]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def flatten_reports(db: Path, root: Path, workflow: str) -> list[dict[str, Any]]:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT w.stage_key,j.id AS job_id,j.job_type,r.id AS run_id,r.output_json
           FROM cortex_workflow_jobs w
           JOIN jobs j ON j.id=w.job_id
           JOIN runs r ON r.job_id=j.id AND r.status='succeeded'
           WHERE w.workflow_id=? ORDER BY w.stage_key""",
        (workflow,),
    ).fetchall()
    connection.close()
    if len(rows) != 102:
        raise ValueError(f"expected 102 successful jobs, found {len(rows)}")
    stages: dict[int, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        session_text, role = row["stage_key"].split(":", 1)
        index = int(session_text[1:])
        output = json.loads(row["output_json"])
        stages[index][role] = {"job_id": row["job_id"], "run_id": row["run_id"], "output": output}
    if sorted(stages) != list(range(51)):
        raise ValueError("workflow does not contain exact sessions s00..s50")

    reports: list[dict[str, Any]] = []
    for index in range(51):
        pair = stages[index]
        if set(pair) != {"train", "evaluate"}:
            raise ValueError(f"session {index} is not a complete train/evaluate pair")
        train_output, eval_output = pair["train"]["output"], pair["evaluate"]["output"]
        train_art = artifact(train_output, "training_report")
        gate_art = artifact(train_output, "gate_credit_report")
        eval_art = artifact(eval_output, "evaluation_report")
        checkpoint_art = artifact(train_output, "checkpoint")
        paths = {
            "training": object_path(root, train_art["sha256"]),
            "gate_credit": object_path(root, gate_art["sha256"]),
            "evaluation": object_path(root, eval_art["sha256"]),
        }
        missing = [str(path) for path in paths.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError("missing retrieved reports: " + ", ".join(missing))
        reports.append(
            {
                "index": index,
                "train_job_id": pair["train"]["job_id"],
                "train_run_id": pair["train"]["run_id"],
                "evaluate_job_id": pair["evaluate"]["job_id"],
                "evaluate_run_id": pair["evaluate"]["run_id"],
                "checkpoint": checkpoint_art,
                "artifacts": {"training": train_art, "gate_credit": gate_art, "evaluation": eval_art},
                "documents": {name: load_json(path) for name, path in paths.items()},
            }
        )
    return reports


def family_aggregate(gate: dict[str, Any]) -> dict[str, dict[str, float | int | None]]:
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    counts: dict[str, int] = defaultdict(int)
    for sample in gate["sampled_steps"]:
        for update in sample.get("parameter_updates", []):
            family = update["family"]
            counts[family] += 1
            for key in (
                "descent_to_optimizer_movement_cosine",
                "gradient_norm",
                "intended_movement_norm",
                "update_to_parameter_norm_ratio",
                "nonfinite_gradient_count",
            ):
                values[family][key].append(float(update[key]))
    return {
        family: {
            "observations": counts[family],
            **{key + "_mean": rounded(mean(samples)) for key, samples in sorted(metrics.items())},
            "nonfinite_gradient_count_sum": int(sum(metrics.get("nonfinite_gradient_count", []))),
        }
        for family, metrics in sorted(values.items())
    }


def gate_aggregate(gate: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, list[float]] = defaultdict(list)
    for sample in gate["sampled_steps"]:
        for layer in sample.get("layers", []):
            for kind in ("raw_gate", "effective_gate"):
                for key in ("density", "mean", "rms", "zero_fraction"):
                    metrics[f"{kind}_{key}"].append(float(layer[kind][key]))
            for kind in ("raw_gate_credit", "effective_gate_credit"):
                for key in (
                    "gate_credit_dot",
                    "gate_credit_cosine",
                    "gradient_to_gate_norm_ratio",
                    "active_strengthening_fraction",
                    "active_suppressing_fraction",
                ):
                    metrics[f"{kind}_{key}"].append(float(layer[kind][key]))
    return {
        "sampled_steps": len(gate["sampled_steps"]),
        "layer_observations": len(next(iter(metrics.values()), [])),
        **{key + "_mean": rounded(mean(samples)) for key, samples in sorted(metrics.items())},
        "effective_credit_positive_fraction": rounded(
            mean(1.0 if value > 0 else 0.0 for value in metrics["effective_gate_credit_gate_credit_dot"])
        ),
        "raw_credit_positive_fraction": rounded(
            mean(1.0 if value > 0 else 0.0 for value in metrics["raw_gate_credit_gate_credit_dot"])
        ),
    }


def session_record(report: dict[str, Any]) -> dict[str, Any]:
    training = report["documents"]["training"]["metadata"]
    gate = report["documents"]["gate_credit"]
    evaluation = report["documents"]["evaluation"]
    summary = evaluation["candidate"]["summary"]
    overall = summary["overall"]
    health = evaluation["candidate"]["scan"]["representation_health"]
    drift = evaluation["certificate"]["representation_drift"]
    losses = [float(value) for value in training["step_losses"]]
    return {
        "session": report["index"],
        "event_count": training["event_count"],
        "duration_seconds": training["duration_seconds"],
        "checkpoint_sha256": report["checkpoint"]["sha256"],
        "checkpoint_bytes": report["checkpoint"]["byte_size"],
        "parent_checkpoint_sha256": training["parent_checkpoint_sha256"],
        "train_job_id": report["train_job_id"],
        "evaluate_job_id": report["evaluate_job_id"],
        "training_report_sha256": report["artifacts"]["training"]["sha256"],
        "gate_credit_report_sha256": report["artifacts"]["gate_credit"]["sha256"],
        "evaluation_report_sha256": report["artifacts"]["evaluation"]["sha256"],
        "loss_first": rounded(losses[0]),
        "loss_last": rounded(losses[-1]),
        "loss_mean": rounded(mean(losses)),
        "loss_min": rounded(min(losses)),
        "loss_max": rounded(max(losses)),
        "heldout_loss": summary["heldout_loss"],
        "passed": overall["passed"],
        "pathological": overall["pathological"],
        "pathological_fraction": rounded(overall["pathological"] / overall["total"]),
        "unique_response_fraction": overall["unique_response_fraction"],
        "dominant_response_fraction": overall["dominant_response_fraction"],
        "capability_pathological": summary["groups"]["capability"]["pathological"],
        "protected_pathological": summary["groups"]["protected"]["pathological"],
        **{f"{name}_drift": drift[name] for name in ("core", "ingress", "intentions")},
        **{f"{name}_separation": health[name]["concept_separation"] for name in ("core", "ingress", "intentions")},
        "gate": gate_aggregate(gate),
        "optimizer_families": family_aggregate(gate),
    }


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    a, b = statistics.fmean(left), statistics.fmean(right)
    numerator = sum((x - a) * (y - b) for x, y in zip(left, right))
    denominator = math.sqrt(sum((x - a) ** 2 for x in left) * sum((y - b) ** 2 for y in right))
    return numerator / denominator if denominator else None


def phase_summary(records: list[dict[str, Any]], indices: range) -> dict[str, Any]:
    selected = [records[index] for index in indices]
    keys = (
        "pathological_fraction", "unique_response_fraction", "heldout_loss",
        "core_drift", "ingress_drift", "intentions_drift",
        "core_separation", "ingress_separation", "intentions_separation",
    )
    return {
        "sessions": [selected[0]["session"], selected[-1]["session"]],
        **{key + "_mean": rounded(mean(float(item[key]) for item in selected)) for key in keys},
    }


def overall_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    path = [float(item["pathological_fraction"]) for item in records]
    keys = ("core_drift", "ingress_drift", "intentions_drift", "core_separation", "ingress_separation", "intentions_separation")
    improvement_steps = sum(path[i] < path[i - 1] for i in range(1, len(path)))
    worsening_steps = sum(path[i] > path[i - 1] for i in range(1, len(path)))
    best = min(records, key=lambda item: (item["pathological_fraction"], -item["unique_response_fraction"]))
    worst = max(records, key=lambda item: (item["pathological_fraction"], -item["unique_response_fraction"]))
    lineage_breaks = [
        records[index]["session"]
        for index in range(1, len(records))
        if records[index]["parent_checkpoint_sha256"] != records[index - 1]["checkpoint_sha256"]
    ]
    gate_keys = sorted(records[0]["gate"])
    gate_summary = {}
    for key in gate_keys:
        if key in {"sampled_steps", "layer_observations"}:
            gate_summary[key + "_sum"] = sum(int(item["gate"][key]) for item in records)
            continue
        values = [float(item["gate"][key]) for item in records if item["gate"][key] is not None]
        gate_summary[key + "_mean"] = rounded(mean(values))
        gate_summary[key + "_correlation_with_session"] = rounded(
            pearson(list(map(float, range(len(values)))), values)
        )
    family_names = sorted({name for item in records for name in item["optimizer_families"]})
    family_summary: dict[str, Any] = {}
    for family in family_names:
        observations = [item["optimizer_families"].get(family) for item in records]
        observations = [item for item in observations if item]
        keys_for_family = sorted({key for item in observations for key in item if key.endswith("_mean")})
        family_summary[family] = {
            "observations": sum(int(item["observations"]) for item in observations),
            "nonfinite_gradient_count_sum": sum(int(item["nonfinite_gradient_count_sum"]) for item in observations),
            **{
                key: rounded(
                    sum(float(item[key]) * int(item["observations"]) for item in observations)
                    / sum(int(item["observations"]) for item in observations)
                )
                for key in keys_for_family
            },
        }
    return {
        "sessions": len(records),
        "events": sum(item["event_count"] for item in records),
        "training_duration_seconds": rounded(sum(item["duration_seconds"] for item in records)),
        "first": {key: records[0][key] for key in ("session", "pathological_fraction", "unique_response_fraction", "heldout_loss", *keys)},
        "last": {key: records[-1][key] for key in ("session", "pathological_fraction", "unique_response_fraction", "heldout_loss", *keys)},
        "best_behavioral_session": {key: best[key] for key in ("session", "pathological_fraction", "unique_response_fraction", "heldout_loss")},
        "worst_behavioral_session": {key: worst[key] for key in ("session", "pathological_fraction", "unique_response_fraction", "heldout_loss")},
        "pathological_fraction_min": min(path),
        "pathological_fraction_max": max(path),
        "pathological_fraction_mean": rounded(mean(path)),
        "pairwise_improvements": improvement_steps,
        "pairwise_regressions": worsening_steps,
        "pairwise_ties": 50 - improvement_steps - worsening_steps,
        "lineage": {
            "first_parent_checkpoint_sha256": records[0]["parent_checkpoint_sha256"],
            "final_checkpoint_sha256": records[-1]["checkpoint_sha256"],
            "chain_continuous": not lineage_breaks,
            "break_sessions": lineage_breaks,
        },
        "phases": {
            "early": phase_summary(records, range(0, 17)),
            "middle": phase_summary(records, range(17, 34)),
            "late": phase_summary(records, range(34, 51)),
        },
        "correlation_with_session": {
            key: rounded(pearson(list(map(float, range(51))), [float(item[key]) for item in records]))
            for key in ("pathological_fraction", "unique_response_fraction", "heldout_loss", *keys)
        },
        "observer": {
            "gate_credit": gate_summary,
            "optimizer_families": family_summary,
        },
    }


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    excluded = {"gate", "optimizer_families"}
    fields = [key for key in records[0] if key not in excluded]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: value for key, value in row.items() if key in fields} for row in records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    reports = flatten_reports(args.db, args.artifact_root, args.workflow)
    records = [session_record(report) for report in reports]
    cumulative_events = 0
    for record in records:
        cumulative_events += int(record["event_count"])
        record["cumulative_events"] = cumulative_events
    result = {
        "schema_version": "ninereeds_campaign35_m5_healing_longitudinal_v1",
        "workflow_id": args.workflow,
        "evidence_completeness": {
            "paired_sessions": len(records),
            "training_reports": len(records),
            "gate_credit_reports": len(records),
            "evaluation_reports": len(records),
        },
        "summary": overall_summary(records),
        "sessions": records,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "m5-healing-longitudinal.json"
    csv_path = args.output_dir / "m5-session-series.csv"
    json_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    write_csv(csv_path, records)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), **result["evidence_completeness"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
