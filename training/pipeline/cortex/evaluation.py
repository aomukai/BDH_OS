from __future__ import annotations

import hashlib
import json
import math
import re
import time
from pathlib import Path
from typing import Any


EVALUATION_SCHEMA = "ninereeds_cortex_candidate_evaluation_v1"
CERTIFICATE_SCHEMA = "ninereeds_cortex_admission_certificate_v1"
_TOKEN = re.compile(r"\w+", re.UNICODE)


class CortexEvaluationError(RuntimeError):
    pass


def load_suite(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "ninereeds_cortex_eval_suite_v1"
        or not isinstance(value.get("suite_id"), str)
        or not isinstance(value.get("cases"), list)
        or not value["cases"]
    ):
        raise CortexEvaluationError("invalid Cortex evaluation suite")
    seen: set[str] = set()
    for case in value["cases"]:
        required = {
            "case_id",
            "group",
            "concept",
            "language",
            "prompt",
            "expected_response",
        }
        if not isinstance(case, dict) or not required.issubset(case):
            raise CortexEvaluationError("evaluation case lacks required fields")
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise CortexEvaluationError("evaluation case IDs must be unique strings")
        seen.add(case_id)
        if case["group"] not in {"capability", "protected"}:
            raise CortexEvaluationError(f"invalid case group: {case_id}")
        for name in ("required_all", "required_any", "forbidden"):
            values = case.get(name, [])
            if not isinstance(values, list) or not all(
                isinstance(item, str) and item for item in values
            ):
                raise CortexEvaluationError(f"invalid {name}: {case_id}")
    return value


def _normalise(text: str) -> str:
    return " ".join(text.casefold().split())


def repetition_metrics(text: str) -> dict[str, Any]:
    tokens = _TOKEN.findall(text.casefold())
    if not tokens:
        return {
            "token_count": 0,
            "dominant_token_fraction": 1.0,
            "repeated_bigram_fraction": 1.0,
            "pathological": True,
        }
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    dominant = max(counts.values()) / len(tokens)
    bigrams = list(zip(tokens, tokens[1:]))
    repeated_bigram = 0.0
    if bigrams:
        unique = len(set(bigrams))
        repeated_bigram = 1.0 - unique / len(bigrams)
    pathological = (
        len(tokens) < 2
        or (len(tokens) >= 4 and dominant >= 0.65)
        or (len(bigrams) >= 3 and repeated_bigram >= 0.66)
        or not text.strip()
    )
    return {
        "token_count": len(tokens),
        "dominant_token_fraction": round(dominant, 6),
        "repeated_bigram_fraction": round(repeated_bigram, 6),
        "pathological": pathological,
    }


def score_response(case: dict[str, Any], response: str) -> dict[str, Any]:
    normalised = _normalise(response)
    required_all = [_normalise(value) for value in case.get("required_all", [])]
    required_any = [_normalise(value) for value in case.get("required_any", [])]
    forbidden = [_normalise(value) for value in case.get("forbidden", [])]
    all_hits = [value for value in required_all if value in normalised]
    any_hits = [value for value in required_any if value in normalised]
    forbidden_hits = [value for value in forbidden if value in normalised]
    repetition = repetition_metrics(response)
    all_fraction = (
        len(all_hits) / len(required_all) if required_all else 1.0
    )
    any_fraction = 1.0 if not required_any or any_hits else 0.0
    score = all_fraction * any_fraction
    if forbidden_hits or repetition["pathological"]:
        score = 0.0
    passed = score == 1.0
    return {
        "score": round(score, 6),
        "passed": passed,
        "required_all_hits": all_hits,
        "required_any_hits": any_hits,
        "forbidden_hits": forbidden_hits,
        "repetition": repetition,
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    concepts: dict[str, list[dict[str, Any]]] = {}
    languages: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        groups.setdefault(case["group"], []).append(case)
        concepts.setdefault(case["concept"], []).append(case)
        languages.setdefault(case["language"], []).append(case)

    def aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
        responses = [
            _normalise(str(item.get("response") or ""))
            for item in items
            if "response" in item
        ]
        dominant_response_fraction = 0.0
        unique_response_fraction = 0.0
        if responses:
            counts: dict[str, int] = {}
            for response in responses:
                counts[response] = counts.get(response, 0) + 1
            dominant_response_fraction = max(counts.values()) / len(responses)
            unique_response_fraction = len(counts) / len(responses)
        return {
            "score": round(_mean([float(item["score"]) for item in items]), 6),
            "passed": sum(bool(item["passed"]) for item in items),
            "total": len(items),
            "pathological": sum(
                bool(item["repetition"]["pathological"]) for item in items
            ),
            "unique_response_fraction": round(unique_response_fraction, 6),
            "dominant_response_fraction": round(
                dominant_response_fraction, 6
            ),
            "cross_prompt_collapse": (
                len(responses) >= 4 and dominant_response_fraction >= 0.6
            ),
        }

    return {
        "overall": aggregate(cases),
        "groups": {key: aggregate(value) for key, value in sorted(groups.items())},
        "concepts": {
            key: aggregate(value) for key, value in sorted(concepts.items())
        },
        "languages": {
            key: aggregate(value) for key, value in sorted(languages.items())
        },
        "heldout_loss": round(
            _mean(
                [
                    float(item["heldout_loss"])
                    for item in cases
                    if math.isfinite(float(item["heldout_loss"]))
                ]
            ),
            6,
        ),
    }


def _activation_summary(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    per_layer: dict[tuple[int, int], list[dict[str, float]]] = {}
    hidden_abs: list[float] = []
    hidden_std: list[float] = []
    for item in diagnostics:
        hidden_abs.append(float(item["hidden_mean_abs"]))
        hidden_std.append(float(item["hidden_std"]))
        for layer in item["layers"]:
            key = (int(layer["tick"]), int(layer["layer"]))
            per_layer.setdefault(key, []).append(layer)
    layers = []
    for (tick, level), rows in sorted(per_layer.items()):
        layers.append(
            {
                "tick": tick,
                "layer": level,
                **{
                    name: round(_mean([float(row[name]) for row in rows]), 8)
                    for name in (
                        "x_sparse_density",
                        "x_sparse_mean_abs",
                        "y_sparse_density",
                        "y_sparse_mean_abs",
                        "xy_sparse_density",
                        "xy_sparse_mean_abs",
                    )
                },
            }
        )
    dead_layers = [
        row["layer"] for row in layers if row["xy_sparse_density"] < 1e-6
    ]
    saturated_layers = [
        row["layer"] for row in layers if row["xy_sparse_density"] > 0.75
    ]
    return {
        "hidden_mean_abs": round(_mean(hidden_abs), 8),
        "hidden_std": round(_mean(hidden_std), 8),
        "dead_layers": sorted(set(dead_layers)),
        "saturated_layers": sorted(set(saturated_layers)),
        "layers": layers,
    }


def _projection(vectors: Any, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import torch

    matrix = torch.stack(vectors).to(torch.float32)
    centered = matrix - matrix.mean(dim=0, keepdim=True)
    if centered.shape[0] < 2 or float(centered.abs().max()) == 0.0:
        coordinates = torch.zeros((centered.shape[0], 3))
    else:
        _, _, right = torch.pca_lowrank(
            centered,
            q=min(3, centered.shape[0], centered.shape[1]),
            center=False,
            niter=4,
        )
        coordinates = centered @ right
        if coordinates.shape[1] < 3:
            coordinates = torch.nn.functional.pad(
                coordinates, (0, 3 - coordinates.shape[1])
            )
    scale = float(coordinates.abs().max()) or 1.0
    coordinates = coordinates / scale
    return [
        {
            "case_id": case["case_id"],
            "group": case["group"],
            "concept": case["concept"],
            "language": case["language"],
            "x": round(float(point[0]), 7),
            "y": round(float(point[1]), 7),
            "z": round(float(point[2]), 7),
        }
        for case, point in zip(cases, coordinates)
    ]


def _representation_health(vectors: Any, cases: list[dict[str, Any]]) -> dict[str, Any]:
    import torch
    import torch.nn.functional as F

    matrix = F.normalize(torch.stack(vectors).to(torch.float32), dim=-1)
    similarities = matrix @ matrix.T
    within: list[float] = []
    between: list[float] = []
    for left in range(len(cases)):
        for right in range(left + 1, len(cases)):
            bucket = (
                within
                if cases[left]["concept"] == cases[right]["concept"]
                else between
            )
            bucket.append(float(similarities[left, right]))
    return {
        "within_concept_cosine": round(_mean(within), 7),
        "between_concept_cosine": round(_mean(between), 7),
        "concept_separation": round(_mean(within) - _mean(between), 7),
    }


def evaluate_checkpoint(
    checkpoint: Path,
    suite: dict[str, Any],
    *,
    ingress_device: str,
    core_device: str,
    max_new_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import torch

    from cortex.student import build_student

    started = time.time()
    torch.manual_seed(0)
    student, parent_kind, _ = build_student(
        checkpoint,
        frozen_dtype=torch.bfloat16,
        local_files_only=True,
    )
    student.place(
        ingress_device=torch.device(ingress_device),
        core_device=torch.device(core_device),
        trainable_dtype=torch.bfloat16,
    )
    student.eval()
    case_results: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    vectors: dict[str, list[Any]] = {"ingress": [], "core": [], "intentions": []}
    with torch.no_grad():
        for case in suite["cases"]:
            trace = student.trace_representations([case["prompt"]])
            expression_parameter = next(student.expression.projector.parameters())
            intentions = trace["intention_tokens"].to(
                device=expression_parameter.device,
                dtype=expression_parameter.dtype,
            )
            generated = student.expression.generate(
                intentions,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
            response = student.expression.tokenizer.batch_decode(
                generated,
                skip_special_tokens=True,
            )[0]
            encoded = student.expression.tokenizer(
                [case["expected_response"]],
                add_special_tokens=False,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            loss = float(
                student.expression.response_loss(
                    intentions,
                    encoded["input_ids"],
                    encoded.get("attention_mask"),
                )
                .detach()
                .cpu()
            )
            scored = score_response(case, response)
            case_results.append(
                {
                    **{
                        key: case[key]
                        for key in (
                            "case_id",
                            "group",
                            "concept",
                            "language",
                            "prompt",
                            "expected_response",
                        )
                    },
                    "response": response,
                    "heldout_loss": round(loss, 7),
                    **scored,
                }
            )
            diagnostics.append(trace["diagnostics"])
            for stage in vectors:
                vectors[stage].append(trace[stage][0])
    result = {
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "parent_kind": parent_kind,
        "summary": _summary(case_results),
        "cases": case_results,
        "scan": {
            "activation_health": _activation_summary(diagnostics),
            "representation_health": {
                stage: _representation_health(values, suite["cases"])
                for stage, values in vectors.items()
            },
            "points": {
                stage: _projection(values, suite["cases"])
                for stage, values in vectors.items()
            },
        },
        "duration_seconds": round(time.time() - started, 3),
    }
    raw = {"vectors": vectors}
    del student
    torch.cuda.empty_cache()
    return result, raw


def compare_evaluations(
    candidate: dict[str, Any],
    candidate_raw: dict[str, Any],
    parent: dict[str, Any],
    parent_raw: dict[str, Any],
    *,
    candidate_checkpoint: str,
    parent_checkpoint: str,
    target_concept: str | None,
) -> dict[str, Any]:
    import torch
    import torch.nn.functional as F

    candidate_summary = candidate["summary"]
    parent_summary = parent["summary"]
    normalized_target = _normalise_target_concept(target_concept)
    target = (
        candidate_summary["concepts"].get(normalized_target)
        if normalized_target
        else None
    )
    parent_target = (
        parent_summary["concepts"].get(normalized_target)
        if normalized_target
        else None
    )
    if target is None:
        target = candidate_summary["groups"]["capability"]
        parent_target = parent_summary["groups"]["capability"]
    protected = candidate_summary["groups"]["protected"]
    parent_protected = parent_summary["groups"]["protected"]
    overall = candidate_summary["overall"]
    parent_overall = parent_summary["overall"]
    pathology_fraction = overall["pathological"] / max(overall["total"], 1)
    reasons: list[str] = []
    failure_modes: list[str] = []
    if pathology_fraction > 0.20:
        reasons.append(
            f"pathological generation rate {pathology_fraction:.1%} exceeds 20%"
        )
        failure_modes.append("expression_repetition_collapse")
    if overall.get("cross_prompt_collapse"):
        pathology_fraction = max(
            pathology_fraction,
            float(overall.get("dominant_response_fraction") or 0),
        )
        reasons.append(
            "cross-prompt generation collapse: one response dominates at least 60% "
            "of the held-out suite"
        )
        failure_modes.append("cross_prompt_generation_collapse")
    if protected["score"] + 0.05 < parent_protected["score"]:
        reasons.append("protected-anchor score regressed by more than 0.05")
        failure_modes.append("protected_behavior_regression")
    if overall["score"] + 0.01 < parent_overall["score"]:
        reasons.append("overall behavioral score regressed")
        failure_modes.append("global_behavior_regression")
    target_gain = float(target["score"]) - float(parent_target["score"])
    if target_gain < 0.05 and float(target["score"]) < 0.80:
        reasons.append(
            "target score neither improved by 0.05 nor reached the 0.80 admission floor"
        )
        failure_modes.append("target_nontransfer")
    if not math.isfinite(float(candidate_summary["heldout_loss"])):
        reasons.append("held-out teacher-forced loss is non-finite")
        failure_modes.append("nonfinite_heldout_loss")
    activation = candidate["scan"]["activation_health"]
    if activation["dead_layers"]:
        reasons.append(f"dead Cortex layers detected: {activation['dead_layers']}")
        failure_modes.append("dead_core_layers")
    if activation["saturated_layers"]:
        reasons.append(
            f"saturated Cortex layers detected: {activation['saturated_layers']}"
        )
        failure_modes.append("saturated_core_layers")

    drift: dict[str, float] = {}
    for stage in ("ingress", "core", "intentions"):
        left = torch.stack(candidate_raw["vectors"][stage]).to(torch.float32)
        right = torch.stack(parent_raw["vectors"][stage]).to(torch.float32)
        cosine = F.cosine_similarity(left, right, dim=-1)
        drift[stage] = round(float((1.0 - cosine).mean()), 8)

    admitted = not reasons
    next_action = _recommended_next_action(failure_modes)
    certificate = {
        "schema_version": CERTIFICATE_SCHEMA,
        "status": "admitted" if admitted else "rejected",
        "candidate_checkpoint": candidate_checkpoint,
        "candidate_sha256": candidate["checkpoint_sha256"],
        "parent_checkpoint": parent_checkpoint,
        "parent_sha256": parent["checkpoint_sha256"],
        "rollback_target": parent_checkpoint,
        "requested_target_concept": target_concept,
        "target_concept": normalized_target,
        "target_score": target["score"],
        "parent_target_score": parent_target["score"],
        "target_gain": round(target_gain, 6),
        "protected_score": protected["score"],
        "parent_protected_score": parent_protected["score"],
        "overall_score": overall["score"],
        "parent_overall_score": parent_overall["score"],
        "pathological_fraction": round(pathology_fraction, 6),
        "representation_drift": drift,
        "failure_modes": failure_modes,
        "reasons": reasons,
        "recommended_next_action": next_action,
        "recommended_parent_checkpoint": (
            candidate_checkpoint if admitted else parent_checkpoint
        ),
    }
    return certificate


def _normalise_target_concept(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.casefold().replace("-", "_")
    aliases = (
        (("cat", "dog", "animal"), "animal"),
        (("inside", "outside", "space"), "space"),
        (("big", "small", "property"), "property"),
        (("unknown", "knowledge_boundary"), "unknown"),
        (("correction",), "correction"),
        (("bag", "box", "container"), "container"),
    )
    for needles, concept in aliases:
        if any(needle in lowered for needle in needles):
            return concept
    return value


def _recommended_next_action(failure_modes: list[str]) -> str:
    modes = set(failure_modes)
    if {
        "expression_repetition_collapse",
        "cross_prompt_generation_collapse",
    } & modes:
        return (
            "Stop concept-curriculum dosing. Run a bounded expression-bridge "
            "bootstrap diagnostic from the rollback checkpoint: compare frozen "
            "LFM text-only behavior with intention-prefix behavior, inspect the "
            "first-token distribution, and train the intention/expression "
            "projectors on a diverse response-opening set before another concept block."
        )
    if "protected_behavior_regression" in modes or "global_behavior_regression" in modes:
        return (
            "Rollback to the certificate target and run a localized repair that "
            "replays protected anchors together with the failed target probes."
        )
    if "target_nontransfer" in modes:
        return (
            "Keep the rollback parent and redesign the smallest target block using "
            "held-out paraphrases and contrasts; do not increase dose until transfer improves."
        )
    if "dead_core_layers" in modes or "saturated_core_layers" in modes:
        return (
            "Keep the rollback parent and run an optimizer/activation-scale diagnostic "
            "before any further language curriculum."
        )
    if "nonfinite_heldout_loss" in modes:
        return "Keep the rollback parent and diagnose numerical stability."
    return "Admit the candidate and use it as the next bounded campaign parent."


def enrich_cross_prompt_metrics(evaluation: dict[str, Any]) -> dict[str, Any]:
    """Backfill deterministic suite-diversity metrics into a stored evaluation."""
    import copy

    value = copy.deepcopy(evaluation)
    for side in ("candidate", "parent"):
        model = value.get(side)
        if (
            isinstance(model, dict)
            and isinstance(model.get("cases"), list)
            and model["cases"]
        ):
            recalculated = _summary(model["cases"])
            existing = model.get("summary")
            if not isinstance(existing, dict):
                model["summary"] = recalculated
                continue
            existing["overall"] = recalculated["overall"]
            for section in ("groups", "languages"):
                current_section = existing.get(section)
                if not isinstance(current_section, dict):
                    current_section = {}
                    existing[section] = current_section
                current_section.update(recalculated[section])
    certificate = value.get("certificate")
    candidate = value.get("candidate")
    if not isinstance(certificate, dict) or not isinstance(candidate, dict):
        return value
    overall = candidate["summary"]["overall"]
    if not overall.get("cross_prompt_collapse"):
        return value
    reason = (
        "cross-prompt generation collapse: one response dominates at least 60% "
        "of the held-out suite"
    )
    reasons = list(certificate.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    modes = list(certificate.get("failure_modes") or [])
    legacy_reason_modes = (
        ("pathological generation rate", "expression_repetition_collapse"),
        ("protected-anchor score regressed", "protected_behavior_regression"),
        ("overall behavioral score regressed", "global_behavior_regression"),
        ("target score neither improved", "target_nontransfer"),
        ("held-out teacher-forced loss is non-finite", "nonfinite_heldout_loss"),
        ("dead Cortex layers detected", "dead_core_layers"),
        ("saturated Cortex layers detected", "saturated_core_layers"),
    )
    for legacy_reason, mode in legacy_reason_modes:
        if any(legacy_reason in item for item in reasons) and mode not in modes:
            modes.append(mode)
    if "cross_prompt_generation_collapse" not in modes:
        modes.append("cross_prompt_generation_collapse")
    certificate["status"] = "rejected"
    certificate["reasons"] = reasons
    certificate["failure_modes"] = modes
    certificate["pathological_fraction"] = max(
        float(certificate.get("pathological_fraction") or 0),
        float(overall["dominant_response_fraction"]),
    )
    certificate["recommended_parent_checkpoint"] = certificate[
        "parent_checkpoint"
    ]
    certificate["recommended_next_action"] = _recommended_next_action(modes)
    return value


def run_candidate_evaluation(
    *,
    candidate_checkpoint: Path,
    parent_checkpoint: Path,
    suite_path: Path,
    campaign_id: str,
    target_concept: str | None,
    ingress_device: str = "cuda:0",
    core_device: str = "cuda:1",
    max_new_tokens: int = 48,
) -> dict[str, Any]:
    suite = load_suite(suite_path)
    candidate, candidate_raw = evaluate_checkpoint(
        candidate_checkpoint,
        suite,
        ingress_device=ingress_device,
        core_device=core_device,
        max_new_tokens=max_new_tokens,
    )
    parent, parent_raw = evaluate_checkpoint(
        parent_checkpoint,
        suite,
        ingress_device=ingress_device,
        core_device=core_device,
        max_new_tokens=max_new_tokens,
    )
    certificate = compare_evaluations(
        candidate,
        candidate_raw,
        parent,
        parent_raw,
        candidate_checkpoint=str(candidate_checkpoint),
        parent_checkpoint=str(parent_checkpoint),
        target_concept=target_concept,
    )
    return {
        "schema_version": EVALUATION_SCHEMA,
        "campaign_id": campaign_id,
        "suite_id": suite["suite_id"],
        "candidate": candidate,
        "parent": parent,
        "certificate": certificate,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
