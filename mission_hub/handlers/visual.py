"""Deterministic visual-pack and multimodal-experience contracts."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
from typing import Any

from ..errors import ProtocolError, RemoteJobError, SafetyError
from ..jsonutil import canonical_json, content_hash
from .contracts import _declaration, _object_file


EVENT_TYPES = {
    "observe_image", "hear_or_read_text", "page_turn", "ask",
    "teacher_correction", "delay", "recall",
}


def _subprocess_text(value: str | bytes | None, fallback: str = "") -> str:
    """Normalize subprocess evidence at the JSON boundary.

    TimeoutExpired may expose captured streams as bytes even when run() was
    called with text=True.  Preserve that evidence without allowing the log
    serializer to mask the original timeout.
    """
    if value is None:
        return fallback
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _local_runtime_failure(returncode: int, stderr: str) -> tuple[str | None, str]:
    """Classify the local model runtime from its preserved machine evidence."""
    detail = stderr.lower()
    if returncode == 75:
        if "disk" in detail or "free space" in detail or "free disk" in detail:
            return "operational_transient", "disk_write_failed"
        if "timed out" in detail or "timeout" in detail:
            return "operational_transient", "process_interrupted"
        return "operational_transient", "resource_temporarily_unavailable"
    if returncode == 69:
        if "import" in detail or "environment unavailable" in detail or "not found in the cached files" in detail:
            return "deterministic_specification", "dependency_missing"
        return "capability_transient", "local_model_capability_unavailable"
    if returncode == 76:
        return "repairable_output", "output_schema_invalid"
    if returncode == 65:
        return "deterministic_specification", "job_spec_invalid"
    return None, "unexpected_internal_error"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_inputs(context: dict[str, Any], requested: list[str]) -> list[dict[str, Any]]:
    artifacts = _artifacts(context, requested)
    roots = [Path(context["state_root"]).resolve(), *(Path(value).resolve() for value in context["artifact_roots"])]
    result = []
    for artifact in artifacts:
        path = Path(artifact["uri"]).resolve()
        if not path.is_file() or not any(path == root or root in path.parents for root in roots):
            raise SafetyError(f"visual input is unavailable or outside configured roots: {artifact['id']}")
        if _sha256(path) != artifact["sha256"] or path.stat().st_size != artifact["byte_size"]:
            raise SafetyError(f"visual input bytes do not match their declaration: {artifact['id']}")
        result.append({
            "id": artifact["id"], "kind": artifact["kind"], "uri": str(path),
            "sha256": artifact["sha256"], "byte_size": artifact["byte_size"],
            "manifest": artifact["manifest"],
        })
    return result


def _runtime_declaration(kind: str, path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind, "sha256": _sha256(path), "byte_size": path.stat().st_size,
        "uri": str(path), "lifecycle": "candidate", "manifest": manifest,
    }


class _VisualRuntimeHandler:
    stage = ""
    required_kinds: tuple[str, ...] = ()
    repeatable_kinds: tuple[str, ...] = ()

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        return None

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        limits = context["visual_limits"]
        inputs = _verified_inputs(context, payload["input_artifact_ids"])
        self.validate_inputs(inputs)
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        request_path = run_root / "request.json"
        result_path = run_root / "result.json"
        request = {
            "schema_version": "ninereeds_visual_runtime_request_v1", "stage": self.stage,
            "run_id": context["run"]["id"], "inputs": inputs,
            "specification": payload["specification"], "request_limits": payload["limits"],
            "configured_limits": limits,
            "prompt": context["prompt"],
        }
        request_path.write_text(json.dumps(request, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        attempts: list[dict[str, Any]] = []
        models = context["route_models"]
        if not models:
            raise SafetyError(f"{self.stage} has no configured model")
        selected: dict[str, Any] | None = None
        for index, model in enumerate(models):
            provider = context["providers"][model["provider"]]
            provider_kind = provider.get("kind", "local_subprocess")
            if not model["enabled"] or not provider["enabled"]:
                raise SafetyError(f"{self.stage} route contains a disabled model or provider")
            if provider_kind == "codex_cli" and self.stage in {"visual.inspect", "visual.caption", "visual.review"}:
                try:
                    transcript = self._codex_batch(
                        provider, model, payload, context, inputs, run_root, result_path,
                        route_attempt_index=index,
                    )
                except Exception as exc:
                    from .visual_provider import ProviderFailure
                    if not isinstance(exc, ProviderFailure):
                        raise
                    attempts.append({
                        "model_id": model["id"], "model_name": model["exact_name"],
                        "revision": model["revision"], "returncode": 69,
                        "failure_class": exc.failure_class, "failure_code": exc.code,
                        "message": str(exc), "transcript": exc.transcript,
                    })
                    if index + 1 >= len(models) or exc.failure_class not in context["route"]["fallback_failure_classes"]:
                        break
                    continue
                attempts.append({
                    "model_id": model["id"], "model_name": model["exact_name"],
                    "revision": model["revision"], "returncode": 0,
                    "failure_class": None, "failure_code": None,
                    "transcript": transcript,
                })
                selected = model
                break
            if provider_kind != "local_subprocess":
                attempts.append({
                    "model_id": model["id"], "model_name": model["exact_name"],
                    "revision": model["revision"], "returncode": 69,
                    "failure_class": "capability_transient",
                    "failure_code": "provider_capability_unavailable",
                    "stderr": f"unsupported visual provider kind: {provider_kind}", "stdout": "",
                })
                if index + 1 >= len(models) or "capability_transient" not in context["route"]["fallback_failure_classes"]:
                    break
                continue
            executable = Path(model["runtime"])
            command = [
                str(executable), str(Path(context["release_root"]) / "meta/scripts/visual_runtime.py"),
                "--request", str(request_path), "--result", str(result_path),
                "--model-id", model["exact_name"], "--revision", model["revision"],
                "--weights-root", model["weights"], "--device", model["device"],
            ]
            environment = dict(os.environ)
            # Each visual model declares an exact auxiliary interpreter.  Its
            # own site-packages must win; the Cortex/Unsloth composite site is
            # Python-version-specific and can shadow this venv with an
            # incompatible Torch build when inherited through PYTHONPATH.
            environment.pop("PYTHONHOME", None)
            environment["PYTHONNOUSERSITE"] = "1"
            environment["PYTHONPATH"] = str(Path(context["release_root"]).resolve())
            try:
                completed = subprocess.run(
                    command, capture_output=True, text=True, env=environment,
                    timeout=min(context["timeout_seconds"], limits["max_stage_seconds"]), check=False,
                )
            except subprocess.TimeoutExpired as exc:
                completed = subprocess.CompletedProcess(
                    command, 75,
                    _subprocess_text(exc.stdout),
                    _subprocess_text(exc.stderr, "visual runtime timed out"),
                )
            except OSError as exc:
                completed = subprocess.CompletedProcess(command, 69, "", f"{type(exc).__name__}: {exc}")
            failure_class, failure_code = _local_runtime_failure(completed.returncode, completed.stderr)
            attempts.append({
                "model_id": model["id"], "model_name": model["exact_name"], "revision": model["revision"],
                "returncode": completed.returncode,
                "failure_class": failure_class,
                "failure_code": failure_code,
                "stdout": completed.stdout, "stderr": completed.stderr,
            })
            if completed.returncode == 0 and result_path.is_file():
                selected = model
                break
            result_path.unlink(missing_ok=True)
            failure_class = attempts[-1]["failure_class"]
            if index + 1 >= len(models) or failure_class not in context["route"]["fallback_failure_classes"]:
                break
        log_path = run_root / "visual-runtime-log.json"
        log_path.write_text(json.dumps({"stage": self.stage, "attempts": attempts}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if selected is None:
            last = attempts[-1]
            detail = str(last.get("stderr") or "").strip()
            summary = f"{self.stage} local runtime failed"
            if detail:
                summary += f": {detail[-2000:]}"
            raise RemoteJobError(
                f"{summary}; evidence: {log_path}",
                failure_class=last.get("failure_class") or "deterministic_specification",
                code=last["failure_code"],
            )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("schema_version") != "ninereeds_visual_runtime_result_v1" or result.get("stage") != self.stage:
            raise ProtocolError("visual runtime returned the wrong stage or schema")
        declarations = []
        for output in result.get("outputs", []):
            kind = output.get("kind")
            path = Path(output.get("uri", "")).resolve()
            if kind not in self.required_kinds or not path.is_file() or run_root not in path.parents:
                raise SafetyError("visual runtime declared an unexpected output")
            manifest = dict(output.get("manifest") or {})
            manifest.update({
                "model_id": selected["exact_name"], "model_revision": selected["revision"],
                "route_id": context["route"]["id"], "run_id": context["run"]["id"],
            })
            declarations.append(_runtime_declaration(kind, path, manifest))
        counts = {
            kind: sum(item["kind"] == kind for item in declarations)
            for kind in self.required_kinds
        }
        invalid_counts = {
            kind: count for kind, count in counts.items()
            if (
                kind in self.repeatable_kinds and count < 1
            ) or (
                kind not in self.repeatable_kinds and count != 1
            )
        }
        if invalid_counts:
            details = ", ".join(f"{kind}={count}" for kind, count in sorted(invalid_counts.items()))
            raise ProtocolError("visual runtime must emit exactly one of each required output kind: " + details)
        self.validate_outputs(declarations, payload)
        declarations.append(_runtime_declaration("log", log_path, {"stage": self.stage, "run_id": context["run"]["id"]}))
        return {
            "status": "succeeded", "stage": self.stage, "metrics": result.get("metrics", {}),
            "artifacts": declarations, "failure": None,
        }

    def validate_outputs(self, declarations: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        return None

    def _codex_batch(
        self, provider: dict[str, Any], model: dict[str, Any], payload: dict[str, Any],
        context: dict[str, Any], inputs: list[dict[str, Any]], run_root: Path,
        result_path: Path, *, route_attempt_index: int,
    ) -> dict[str, Any]:
        """Run one schema-bound Codex image request per verified candidate."""
        from .visual_provider import ProviderFailure, _codex, _render_prompt
        from ..schema import load_schema, validate

        candidates = [item for item in inputs if item["kind"] == "visual_candidate"]
        if not candidates:
            raise SafetyError(f"{self.stage} requires candidate pixels")
        prompt = context.get("prompt")
        if not prompt:
            raise SafetyError(f"{self.stage} has no configured prompt")
        repo_root = Path(context["release_root"]).resolve()
        schema_path = (repo_root / prompt["output_schema"]).resolve()
        schema = load_schema(repo_root, prompt["output_schema"])
        base_prompt = _render_prompt(prompt, payload, inputs, self.stage)
        rows, transcripts = [], []
        for index, candidate in enumerate(candidates):
            # A fallback model is a separate provider attempt.  Keep its
            # workspace separate from the prior model's preserved evidence.
            call_root = run_root / f"codex-{route_attempt_index:02d}-{index:04d}"
            call_root.mkdir()
            task = (
                base_prompt
                + "\n\nAnalyze only the attached verified image. Its declared SHA-256 is "
                + candidate["sha256"]
                + ". Return only the requested JSON object."
            )
            value, transcript = _codex(
                provider, model, task, schema_path, [Path(candidate["uri"])], call_root,
            )
            errors = validate(value, schema)
            if errors:
                raise ProviderFailure(
                    "Codex visual output failed schema validation: " + "; ".join(errors),
                    "repairable_output", transcript=transcript,
                )
            if self.stage == "visual.review":
                value["asset_sha256"] = candidate["sha256"]
            rows.append({"asset_sha256": candidate["sha256"], "result": value})
            transcripts.append({"asset_sha256": candidate["sha256"], **transcript})

        if self.stage == "visual.review":
            path = run_root / "review-report.json"
            report = {
                "schema_version": "ninereeds_visual_review_batch_v1",
                "items": rows,
            }
            path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            outputs = [{
                "kind": "visual_review_report", "uri": str(path),
                "manifest": {
                    **report, "item_count": len(rows),
                    "reviewer": model["exact_name"], "independent_review": True,
                },
            }]
        else:
            report_kind = "visual_inspection_report" if self.stage == "visual.inspect" else "visual_caption_report"
            report_path = run_root / ("inspection-report.json" if self.stage == "visual.inspect" else "caption-report.json")
            report_path.write_text(json.dumps({
                "schema_version": f"ninereeds_{self.stage.replace('.', '_')}_v1", "items": rows,
            }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            outputs = [{"kind": report_kind, "uri": str(report_path), "manifest": {"item_count": len(rows)}}]
        transcript_path = run_root / "provider-transcript.json"
        transcript_path.write_text(json.dumps({
            "schema_version": "ninereeds_provider_transcript_v1", "items": transcripts,
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        outputs.append({"kind": "provider_transcript", "uri": str(transcript_path), "manifest": {"item_count": len(rows)}})
        result_path.write_text(json.dumps({
            "schema_version": "ninereeds_visual_runtime_result_v1", "stage": self.stage,
            "outputs": outputs, "metrics": {"items": len(rows), "provider": "codex_cli"},
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return {"items": transcripts}


class VisualGenerateHandler(_VisualRuntimeHandler):
    stage = "visual.generate"
    required_kinds = ("visual_candidate", "visual_generation_report")
    repeatable_kinds = ("visual_candidate",)

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        if [item["kind"] for item in inputs].count("visual_plan") != 1 or len(inputs) != 1:
            raise SafetyError("visual generation requires exactly one immutable visual plan")

    def validate_outputs(self, declarations: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        selection = payload["specification"].get("selection")
        if selection is not None and sum(item["kind"] == "visual_candidate" for item in declarations) != 1:
            raise ProtocolError("single-candidate generation must emit exactly one visual candidate")


class VisualExactPlanHandler:
    """Freeze a reviewed config-supplied plan without asking a model to rewrite it."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if payload["input_artifact_ids"]:
            raise SafetyError("an exact visual plan does not accept predecessor artifacts")
        plan = payload["specification"]
        authority = plan.get("authority", {})
        if authority.get("exact_material") is not True or authority.get("campaign_id") != context["campaign_id"]:
            raise SafetyError("exact visual planning requires campaign-bound reviewed material authority")
        items = plan.get("items")
        if not isinstance(items, list) or not items or len(items) > payload["limits"]["max_pack_items"]:
            raise SafetyError("exact visual plan exceeds its item bound")
        if any(not str(item.get("item_id") or "").strip() or not str(item.get("prompt") or "").strip() for item in items):
            raise SafetyError("exact visual plan contains an incomplete item")
        path, digest, size = _object_file(
            context["state_root"], (canonical_json(plan) + "\n").encode("utf-8"),
        )
        return {
            "status": "succeeded", "stage": "visual.plan_exact",
            "metrics": {"items": len(items)},
            "artifacts": [_declaration("visual_plan", path, digest, size, {
                **plan, "schema_version": "ninereeds_exact_visual_plan_v1",
            })], "failure": None,
        }


class VisualInspectHandler(_VisualRuntimeHandler):
    stage = "visual.inspect"
    required_kinds = ("visual_inspection_report", "provider_transcript")

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        kinds = [item["kind"] for item in inputs]
        if not kinds.count("visual_candidate") or kinds.count("visual_generation_report") != 1 or any(kind not in {"visual_candidate", "visual_generation_report"} for kind in kinds):
            raise SafetyError("visual inspection requires candidates and exactly one generation report")


class VisualCaptionHandler(_VisualRuntimeHandler):
    stage = "visual.caption"
    required_kinds = ("visual_caption_report", "provider_transcript")

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        kinds = [item["kind"] for item in inputs]
        if not kinds.count("visual_candidate") or kinds.count("visual_inspection_report") != 1 or any(kind not in {"visual_candidate", "visual_inspection_report"} for kind in kinds):
            raise SafetyError("visual captioning requires candidates and exactly one inspection report")


class VisualReviewRuntimeHandler(_VisualRuntimeHandler):
    stage = "visual.review"
    required_kinds = ("visual_review_report", "provider_transcript")

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        kinds = [item["kind"] for item in inputs]
        if (
            not kinds.count("visual_candidate")
            or kinds.count("visual_inspection_report") != 1
            or kinds.count("visual_decision_report") != 1
            or any(kind not in {"visual_candidate", "visual_inspection_report", "visual_decision_report"} for kind in kinds)
        ):
            raise SafetyError("independent batch review requires candidates, inspection evidence, and one policy decision")


class VisualEncodeHandler(_VisualRuntimeHandler):
    stage = "visual.encode"
    required_kinds = ("visual_features",)

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        kinds = [item["kind"] for item in inputs]
        if not kinds.count("visual_candidate") or kinds.count("visual_pack") != 1 or any(kind not in {"visual_candidate", "visual_pack"} for kind in kinds):
            raise SafetyError("visual encoding requires one accepted pack and its exact candidates")

    def validate_outputs(self, declarations: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        selection = payload["specification"].get("selection")
        if selection is None:
            return
        features = [item for item in declarations if item["kind"] == "visual_features"]
        if len(features) != 1 or features[0]["manifest"].get("asset_sha256") != [selection["asset_sha256"]]:
            raise ProtocolError("single-candidate encoding output disagrees with its immutable selection")


class VisualFeaturesFinalizeHandler:
    """Combine independently encoded feature shards without model inference."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        import numpy as np

        artifacts = _verified_inputs(context, payload["input_artifact_ids"])
        packs = [item for item in artifacts if item["kind"] == "visual_pack"]
        shards = [item for item in artifacts if item["kind"] == "visual_features"]
        if len(packs) != 1 or not shards:
            raise SafetyError("feature finalization requires one accepted pack and feature shards")
        accepted = [item["asset_sha256"] for item in packs[0]["manifest"].get("items", [])]
        by_hash: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for shard in shards:
            hashes = shard["manifest"].get("asset_sha256")
            if not isinstance(hashes, list) or len(hashes) != 1 or hashes[0] in by_hash:
                raise SafetyError("feature finalization requires one unique asset per shard")
            with np.load(shard["uri"], allow_pickle=False) as loaded:
                required = {"patch_0000", "mask_0000", "shape_0000", "asset_sha256"}
                if not required <= set(loaded.files):
                    raise SafetyError("feature shard is missing required arrays")
                stored = [str(value) for value in loaded["asset_sha256"].tolist()]
                if stored != hashes:
                    raise SafetyError("feature shard array identity disagrees with its manifest")
                by_hash[hashes[0]] = (shard, {
                    "patch": loaded["patch_0000"].copy(),
                    "mask": loaded["mask_0000"].copy(),
                    "shape": loaded["shape_0000"].copy(),
                })
        if set(by_hash) != set(accepted) or len(by_hash) != len(accepted):
            raise SafetyError("feature shards do not exactly cover the accepted pack")
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        arrays: dict[str, Any] = {}
        for index, digest in enumerate(accepted):
            arrays[f"patch_{index:04d}"] = by_hash[digest][1]["patch"]
            arrays[f"mask_{index:04d}"] = by_hash[digest][1]["mask"]
            arrays[f"shape_{index:04d}"] = by_hash[digest][1]["shape"]
        path = run_root / "visual-features.npz"
        np.savez_compressed(path, asset_sha256=np.asarray(accepted), **arrays)
        manifest = {
            "schema_version": "ninereeds_visual_features_v1", "asset_sha256": accepted,
            "count": len(accepted), "format": "npz-no-pickle",
            "feature_kind": "siglip2_last_hidden_state",
            "feature_width": int(arrays["patch_0000"].shape[-1]),
            "includes_patch_mask": True, "includes_spatial_shapes": True,
            "source_shard_artifact_ids": [by_hash[digest][0]["id"] for digest in accepted],
        }
        return {
            "status": "succeeded", "stage": "visual.features_finalize",
            "metrics": {"items": len(accepted), "feature_width": manifest["feature_width"]},
            "artifacts": [_runtime_declaration("visual_features", path, manifest)], "failure": None,
        }


def _artifacts(context: dict[str, Any], requested: list[str]) -> list[dict[str, Any]]:
    indexed = {artifact["id"]: artifact for artifact in context["artifacts"]}
    if len(requested) != len(set(requested)):
        raise SafetyError("visual stage repeats an input artifact")
    missing = [artifact_id for artifact_id in requested if artifact_id not in indexed]
    if missing:
        raise ProtocolError("visual stage did not receive artifacts: " + ", ".join(missing))
    return [indexed[artifact_id] for artifact_id in requested]


def _review_evidence(review: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand one physical review artifact into its per-asset evidence rows."""
    manifest = review.get("manifest", {})
    items = manifest.get("items")
    if not isinstance(items, list):
        return [{"artifact": review, "manifest": manifest}]
    common = {
        key: manifest[key]
        for key in ("reviewer", "independent_review")
        if key in manifest
    }
    evidence = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("result"), dict):
            raise SafetyError("visual review batch contains malformed evidence")
        result = dict(item["result"])
        digest = item.get("asset_sha256")
        if result.get("asset_sha256") != digest:
            raise SafetyError("visual review batch row has inconsistent asset hashes")
        evidence.append({"artifact": review, "manifest": {**common, **result}})
    if not evidence:
        raise SafetyError("visual review batch contains no evidence")
    return evidence


class VisualPackFinalizeHandler:
    """Create a pack only when every candidate has an independent usable review."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if context["visual_limits"]["shadow_mode"]:
            raise SafetyError("visual pack finalization is blocked while shadow mode is on")
        artifacts = _artifacts(context, payload["input_artifact_ids"])
        candidates = {item["sha256"]: item for item in artifacts if item["kind"] == "visual_candidate"}
        reviews = [item for item in artifacts if item["kind"] == "visual_review_report"]
        if not candidates or not reviews:
            raise SafetyError("visual pack requires candidate pixels and independent review reports")
        if len(candidates) > context["visual_limits"]["max_pack_items"]:
            raise SafetyError("visual pack exceeds configured item limit")
        if sum(item["byte_size"] for item in candidates.values()) > context["visual_limits"]["max_pack_bytes"]:
            raise SafetyError("visual pack exceeds configured byte ceiling")
        accepted: dict[str, dict[str, Any]] = {}
        for review in reviews:
            is_batch = isinstance(review.get("manifest", {}).get("items"), list)
            for evidence in _review_evidence(review):
                manifest = evidence["manifest"]
                digest = manifest.get("asset_sha256")
                if digest not in candidates:
                    if is_batch:
                        continue
                    raise SafetyError("visual review names a candidate outside this pack")
                independent = manifest.get("independent_review") is True or manifest.get("reviewer") == "sol"
                if not independent or manifest.get("asset_status") != "usable":
                    continue
                uses = manifest.get("accepted_uses")
                if not isinstance(uses, list) or not uses:
                    raise SafetyError("usable visual review requires exact accepted uses")
                if digest in accepted:
                    raise SafetyError("visual candidate has more than one usable admission review")
                accepted[digest] = {"review_artifact_id": review["id"], "accepted_uses": uses}
        if set(accepted) != set(candidates):
            raise SafetyError("every visual candidate must have one usable independent review")
        manifest = {
            "schema_version": "ninereeds_visual_pack_manifest_v1",
            "pack_id": payload["specification"].get("pack_id") or f"pack-{content_hash(sorted(candidates))[:16]}",
            "status": "accepted",
            "items": [
                {
                    "asset_artifact_id": candidates[digest]["id"], "asset_sha256": digest,
                    "byte_size": candidates[digest]["byte_size"],
                    "item_id": candidates[digest]["manifest"].get("item_id"),
                    "seed": candidates[digest]["manifest"].get("seed"),
                    **accepted[digest],
                }
                for digest in sorted(candidates)
            ],
            "source_artifact_ids": payload["input_artifact_ids"],
            "independent_review_required": True,
        }
        path, digest, size = _object_file(
            context["state_root"], (canonical_json(manifest) + "\n").encode("utf-8"),
        )
        return {
            "status": "succeeded", "stage": "visual.pack_finalize",
            "metrics": {"accepted_items": len(candidates), "pack_sha256": digest},
            "artifacts": [_declaration("visual_pack", path, digest, size, manifest)], "failure": None,
        }


class VisualExperienceCompileHandler:
    """Compile ordered image/text events without embedding pixels or encoder features."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        artifacts = _artifacts(context, payload["input_artifact_ids"])
        packs = [item for item in artifacts if item["kind"] == "visual_pack"]
        if len(packs) != 1:
            raise SafetyError("visual experience requires exactly one accepted pack")
        pack = packs[0]
        if pack["manifest"].get("status") != "accepted":
            raise SafetyError("visual experience pack is not accepted")
        accepted_hashes = {item["asset_sha256"] for item in pack["manifest"].get("items", [])}
        hashes_by_item = {
            item.get("item_id"): item["asset_sha256"]
            for item in pack["manifest"].get("items", [])
            if item.get("item_id")
        }
        events = payload["specification"].get("events")
        if not isinstance(events, list) or not events:
            raise SafetyError("visual experience requires ordered events")
        checked = []
        for index, event in enumerate(events):
            if not isinstance(event, dict) or event.get("type") not in EVENT_TYPES:
                raise SafetyError(f"visual experience event {index} has an unsupported type")
            event = dict(event)
            if event["type"] == "observe_image":
                if "asset_sha256" not in event and event.get("asset_item_id") in hashes_by_item:
                    event["asset_sha256"] = hashes_by_item[event.pop("asset_item_id")]
                if event.get("asset_sha256") not in accepted_hashes:
                    raise SafetyError(f"visual experience event {index} names an unaccepted image")
            if event["type"] in {"hear_or_read_text", "ask", "teacher_correction", "recall"} and not str(event.get("text") or "").strip():
                raise SafetyError(f"visual experience event {index} requires canonical text")
            checked.append(event)
        manifest = {
            "schema_version": "ninereeds_msm_experience_v1",
            "experience_id": payload["specification"].get("experience_id") or f"experience-{content_hash(checked)[:16]}",
            "visual_pack_artifact_id": pack["id"], "visual_pack_sha256": pack["sha256"],
            "events": checked,
        }
        path, digest, size = _object_file(
            context["state_root"], (canonical_json(manifest) + "\n").encode("utf-8"),
        )
        return {
            "status": "succeeded", "stage": "visual.experience_compile",
            "metrics": {"events": len(checked), "experience_sha256": digest},
            "artifacts": [_declaration("visual_experience", path, digest, size, manifest)], "failure": None,
        }
