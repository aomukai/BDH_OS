from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_SCHEMA = "ninereeds_cortex_development_state_v1"
POLICY_SCHEMA = "ninereeds_cortex_development_policy_v1"
FULL_CORE_PARAMETER_FLOOR = 1_000_000_000
_SURFACE_WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
_JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_GERMAN_MARKERS = {
    "aber",
    "auf",
    "das",
    "dem",
    "den",
    "der",
    "die",
    "ein",
    "eine",
    "einen",
    "einer",
    "es",
    "für",
    "haben",
    "hat",
    "ich",
    "ist",
    "kann",
    "können",
    "mit",
    "nicht",
    "oder",
    "sind",
    "soll",
    "sollte",
    "und",
    "warum",
    "was",
    "welche",
    "wenn",
    "wie",
    "zu",
}


class DevelopmentStateError(RuntimeError):
    pass


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class DevelopmentStateStore:
    """Rebuild compact developmental awareness from durable control evidence."""

    def __init__(
        self,
        repo_root: Path,
        *,
        reports_dir: Path | None = None,
        plans_dir: Path | None = None,
        state_path: Path | None = None,
        policy_path: Path | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.reports_dir = (
            reports_dir.resolve()
            if reports_dir is not None
            else Path(
                os.environ.get(
                    "NINEREEDS_ORCHESTRATOR_CONTROL_ROOT",
                    "/home/aomukai/.local/state/ninereeds-orchestrator-control",
                )
            ).resolve()
            / "reports"
        )
        self.plans_dir = (
            plans_dir.resolve()
            if plans_dir is not None
            else self.reports_dir.parent / "plans"
        )
        self.state_path = (
            state_path.resolve()
            if state_path is not None
            else self.repo_root / "training/logs/cortex_development_state.json"
        )
        self.policy_path = (
            policy_path.resolve()
            if policy_path is not None
            else self._default_policy_path()
        )

    def _default_policy_path(self) -> Path:
        repository_policy = (
            self.repo_root / "training/pipeline/cortex/development_policy.json"
        )
        if repository_policy.is_file():
            return repository_policy
        return Path(__file__).with_name("development_policy.json").resolve()

    def policy(self) -> dict[str, Any]:
        try:
            value = json.loads(self.policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DevelopmentStateError(f"cannot read development policy: {exc}") from exc
        required = {
            "schema_version",
            "architecture",
            "stages",
            "foundational_readiness",
            "policy_notes",
        }
        if (
            not isinstance(value, dict)
            or set(value) != required
            or value["schema_version"] != POLICY_SCHEMA
            or not isinstance(value["stages"], list)
            or value["stages"][:2] != ["commissioning", "foundational_bootstrap"]
            or not isinstance(value["foundational_readiness"], dict)
        ):
            raise DevelopmentStateError("invalid Cortex development policy")
        return value

    def read(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise DevelopmentStateError(f"cannot read development state: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != STATE_SCHEMA:
            raise DevelopmentStateError("invalid Cortex development state")
        return value

    def reconcile(self) -> dict[str, Any]:
        state = self.reconstruct()
        self._write(state)
        return state

    def reconstruct(self) -> dict[str, Any]:
        policy = self.policy()
        architecture = policy["architecture"]
        reports = self._reports()
        blocks: list[dict[str, Any]] = []
        all_evaluations: list[dict[str, Any]] = []
        for report in reports:
            result = report.get("result")
            if not isinstance(result, dict) or result.get("status") != "completed":
                continue
            if result.get("kind") == "cortex_block":
                metadata = result.get("metadata")
                if (
                    isinstance(metadata, dict)
                    and metadata.get("architecture") == architecture
                ):
                    blocks.append(report)
            elif result.get("kind") == "cortex_evaluation":
                all_evaluations.append(report)

        architecture_checkpoints = {
            checkpoint
            for checkpoint in (
                _string_or_none(report["result"].get("checkpoint_after"))
                for report in blocks
            )
            if checkpoint is not None
        }
        evaluations: list[dict[str, Any]] = []
        for report in all_evaluations:
            result = report["result"]
            certificate = result.get("certificate")
            if not isinstance(certificate, dict):
                evaluation = result.get("evaluation")
                certificate = (
                    evaluation.get("certificate")
                    if isinstance(evaluation, dict)
                    else None
                )
            if not isinstance(certificate, dict):
                continue
            referenced = {
                checkpoint
                for checkpoint in (
                    _string_or_none(certificate.get("candidate_checkpoint")),
                    _string_or_none(certificate.get("parent_checkpoint")),
                    _string_or_none(
                        certificate.get("recommended_parent_checkpoint")
                    ),
                )
                if checkpoint is not None
            }
            if referenced & architecture_checkpoints:
                evaluations.append(report)

        certificate_counts = {
            "admitted": 0,
            "developmental_progress": 0,
            "rejected": 0,
        }
        current_checkpoint = next(
            (
                checkpoint
                for checkpoint in (
                    _string_or_none(report.get("result", {}).get("checkpoint_after"))
                    for report in reversed(blocks)
                )
                if checkpoint is not None
            ),
            None,
        )
        rollback_checkpoint: str | None = None
        latest_certificate: dict[str, Any] | None = None
        parents: dict[str, str] = {}
        for report in evaluations:
            result = report["result"]
            certificate = result.get("certificate")
            if not isinstance(certificate, dict):
                evaluation = result.get("evaluation")
                certificate = (
                    evaluation.get("certificate")
                    if isinstance(evaluation, dict)
                    else None
                )
            if not isinstance(certificate, dict):
                continue
            latest_certificate = certificate
            status = certificate.get("status")
            if status in certificate_counts:
                certificate_counts[status] += 1
            recommended = _string_or_none(
                certificate.get("recommended_parent_checkpoint")
            )
            if recommended is not None:
                current_checkpoint = recommended
            rollback_checkpoint = _string_or_none(certificate.get("rollback_target"))
            candidate = _string_or_none(certificate.get("candidate_checkpoint"))
            parent = _string_or_none(certificate.get("parent_checkpoint"))
            if candidate is not None and parent is not None:
                parents[candidate] = parent

        lineage: set[str] = set()
        cursor = current_checkpoint
        while cursor is not None and cursor not in lineage:
            lineage.add(cursor)
            cursor = parents.get(cursor)

        concepts: set[str] = set()
        prompt_words: set[str] = set()
        response_words: set[str] = set()
        language_examples: dict[str, int] = {}
        language_word_exposures: dict[str, int] = {}
        documented_lexical_examples = 0
        total_steps = full_core_steps = bridge_steps = examples_seen = 0
        full_core_blocks = bridge_blocks = 0
        for report in blocks:
            result = report["result"]
            checkpoint = _string_or_none(result.get("checkpoint_after"))
            if checkpoint is None or (lineage and checkpoint not in lineage):
                continue
            metadata = result.get("metadata")
            if not isinstance(metadata, dict):
                continue
            steps = metadata.get("step_losses")
            step_count = len(steps) if isinstance(steps, list) else 0
            if step_count == 0:
                examples = _nonnegative_int(metadata.get("examples"))
                epochs = _nonnegative_int(metadata.get("epochs"))
                batch = max(_nonnegative_int(metadata.get("batch_size")), 1)
                step_count = (examples * epochs + batch - 1) // batch
            total_steps += step_count
            examples_seen += (
                _nonnegative_int(metadata.get("examples"))
                * max(_nonnegative_int(metadata.get("epochs")), 1)
            )
            epochs = max(_nonnegative_int(metadata.get("epochs")), 1)
            examples = self._plan_examples(str(report.get("plan_id") or ""))
            documented_lexical_examples += len(examples) * epochs
            for prompt, response in examples:
                prompt_tokens = _surface_words(prompt)
                response_tokens = _surface_words(response)
                prompt_words.update(token.casefold() for token in prompt_tokens)
                response_words.update(token.casefold() for token in response_tokens)
                language = _language(prompt, response)
                language_examples[language] = (
                    language_examples.get(language, 0) + epochs
                )
                language_word_exposures[language] = (
                    language_word_exposures.get(language, 0)
                    + (len(prompt_tokens) + len(response_tokens)) * epochs
                )
            source = metadata.get("training_source")
            concept = source.get("concept") if isinstance(source, dict) else None
            if isinstance(concept, str) and concept:
                concepts.add(concept)
            ownership = metadata.get("ownership")
            trainable = (
                _nonnegative_int(ownership.get("trainable_parameters"))
                if isinstance(ownership, dict)
                else 0
            )
            if trainable >= FULL_CORE_PARAMETER_FLOOR:
                full_core_blocks += 1
                full_core_steps += step_count
            else:
                bridge_blocks += 1
                bridge_steps += step_count

        readiness = policy["foundational_readiness"]
        observed = {
            "full_core_optimizer_steps": full_core_steps,
            "full_core_blocks": full_core_blocks,
            "unique_curriculum_concepts": len(concepts),
            "examples_seen": examples_seen,
        }
        required = {
            "full_core_optimizer_steps": int(
                readiness["minimum_full_core_optimizer_steps"]
            ),
            "full_core_blocks": int(readiness["minimum_full_core_blocks"]),
            "unique_curriculum_concepts": int(
                readiness["minimum_unique_curriculum_concepts"]
            ),
            "examples_seen": int(readiness["minimum_examples_seen"]),
        }
        gates = {
            key: {
                "observed": observed[key],
                "required": required[key],
                "met": observed[key] >= required[key],
            }
            for key in observed
        }
        if not blocks:
            stage = "commissioning"
        elif all(gate["met"] for gate in gates.values()):
            stage = "language_stabilization"
        else:
            stage = "foundational_bootstrap"

        if stage == "commissioning":
            expected_behavior = (
                "No learned Cortex behavior is expected until a full-core bootstrap "
                "checkpoint exists."
            )
            next_action = "Commission one numerically safe full-core bootstrap block."
        elif stage == "foundational_bootstrap":
            expected_behavior = (
                "Coherent chat is not yet expected from the randomly initialized 1.2B "
                "core. Generated text is diagnostic evidence, not an admission gate."
            )
            next_action = (
                "Continue deterministic 500-example foundational replay blocks from the "
                "current developmental checkpoint, using the 65% replay / 25% new / 10% "
                "boundary-and-multilingual mix, until the lineage reaches the 10,000-example "
                "foundation floor. Evaluate after each block; do not return to six-item "
                "blocks or substitute a bridge-only concept repair. Keep the active ingress "
                "limit at 512 tokens during this controlled bootstrap; do not interrupt or "
                "restart the lineage merely to expand context. Before full K-8 lesson "
                "training, commission a separate long-context ingress experiment that lets "
                "the LFM2.5 Encoder consume up to its trained 8,192-token window and uses "
                "bounded compression or hierarchical chunking before the quadratic "
                "Ninereeds/BDH core. A successful context expansion must remain compatible "
                "with the learned core lineage."
            )
        else:
            expected_behavior = (
                "Begin enforcing language stability while retaining structural and "
                "optimization-health gates."
            )
            next_action = (
                "Run a broad language-stabilization block and evaluate behavioral trend."
            )

        stages = policy["stages"]
        all_words = prompt_words | response_words
        language_total = sum(language_examples.values())
        language_mix = {
            language: {
                "examples": count,
                "example_fraction": (
                    round(count / language_total, 6) if language_total else 0.0
                ),
                "word_exposures": language_word_exposures.get(language, 0),
            }
            for language, count in sorted(language_examples.items())
        }
        return {
            "schema_version": STATE_SCHEMA,
            "architecture": architecture,
            "components": {
                "ingress": {
                    "model": "LFM2.5 Encoder 230M",
                    "origin": "pretrained",
                    "training": "frozen",
                },
                "core": {
                    "model": "Ninereeds 1.2B",
                    "origin": "random initialization at lineage root",
                    "training": "full-core during foundational bootstrap",
                },
                "expression": {
                    "model": "LFM2.5 230M",
                    "origin": "pretrained",
                    "training": "frozen; projectors may be trained",
                },
            },
            "stage": stage,
            "stage_index": stages.index(stage),
            "current_checkpoint": current_checkpoint,
            "rollback_checkpoint": rollback_checkpoint,
            "evidence": {
                "completed_blocks": full_core_blocks + bridge_blocks,
                "all_experimental_blocks": len(blocks),
                "full_core_blocks": full_core_blocks,
                "bridge_only_blocks": bridge_blocks,
                "total_optimizer_steps": total_steps,
                "full_core_optimizer_steps": full_core_steps,
                "bridge_only_optimizer_steps": bridge_steps,
                "examples_seen": examples_seen,
                "lexical_exposure": {
                    "documented_examples": documented_lexical_examples,
                    "unaccounted_examples": max(
                        0, examples_seen - documented_lexical_examples
                    ),
                    "total_word_exposures": sum(
                        language_word_exposures.values()
                    ),
                    "unique_surface_word_types": len(all_words),
                    "unique_prompt_word_types": len(prompt_words),
                    "unique_response_word_types": len(response_words),
                    "language_mix": language_mix,
                },
                "curriculum_concepts": sorted(concepts),
                "evaluations": len(evaluations),
                **{f"{key}_certificates": value for key, value in certificate_counts.items()},
            },
            "readiness_gates": gates,
            "behavioral_admission_eligible": stage not in {
                "commissioning",
                "foundational_bootstrap",
            },
            "expected_behavior": expected_behavior,
            "prohibited_actions": (
                [
                    "promote a checkpoint as a winner",
                    "rollback solely because generated chat is incoherent",
                    "use expression-bridge-only training as the primary curriculum",
                    "infer maturity from reduced training loss alone",
                ]
                if stage == "foundational_bootstrap"
                else ["infer maturity from reduced training loss alone"]
            ),
            "recommended_next_action": next_action,
            "latest_certificate": latest_certificate,
            "source": {
                "reports_dir": str(self.reports_dir),
                "plans_dir": str(self.plans_dir),
                "policy_path": _display_path(self.policy_path, self.repo_root),
                "report_count": len(reports),
            },
            "updated_at": utc_now(),
        }

    def _plan_examples(self, plan_id: str) -> list[tuple[str, str]]:
        if not plan_id:
            return []
        path = self.plans_dir / f"{plan_id}.json"
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        payload = plan.get("payload") if isinstance(plan, dict) else None
        if not isinstance(payload, dict):
            return []
        script = payload.get("script")
        if isinstance(script, dict):
            return _script_examples(script)
        curriculum_id = payload.get("curriculum_id")
        jsonl_paths = payload.get("jsonl_paths")
        if (
            isinstance(curriculum_id, str)
            and isinstance(jsonl_paths, list)
            and all(isinstance(value, str) for value in jsonl_paths)
        ):
            examples: list[tuple[str, str]] = []
            for chunk_plan_path in sorted(self.plans_dir.glob("*.json")):
                try:
                    chunk_plan = json.loads(
                        chunk_plan_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    continue
                chunk_payload = (
                    chunk_plan.get("payload")
                    if isinstance(chunk_plan, dict)
                    else None
                )
                if (
                    chunk_plan.get("kind") != "cortex_corpus_chunk"
                    or not isinstance(chunk_payload, dict)
                    or chunk_payload.get("curriculum_id") != curriculum_id
                ):
                    continue
                for value in chunk_payload.get("examples") or []:
                    if (
                        isinstance(value, dict)
                        and isinstance(value.get("prompt"), str)
                        and isinstance(value.get("completion"), str)
                    ):
                        examples.append((value["prompt"], value["completion"]))
            return examples
        jsonl_path = payload.get("jsonl_path")
        if not isinstance(jsonl_path, str):
            return []
        source = (self.repo_root / jsonl_path).resolve()
        if self.repo_root not in source.parents or not source.is_file():
            return []
        examples: list[tuple[str, str]] = []
        try:
            with source.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if (
                        isinstance(value, dict)
                        and isinstance(value.get("prompt"), str)
                        and isinstance(value.get("completion"), str)
                    ):
                        examples.append((value["prompt"], value["completion"]))
        except (OSError, json.JSONDecodeError):
            return []
        return examples

    def _reports(self) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        if not self.reports_dir.is_dir():
            return reports
        for path in self.reports_dir.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                reports.append(value)
        reports.sort(
            key=lambda value: (
                str(value.get("completed_at") or ""),
                str(value.get("plan_id") or ""),
            )
        )
        return reports

    def _write(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.", dir=self.state_path.parent
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.state_path)
        finally:
            temporary.unlink(missing_ok=True)


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return max(int(value), 0)


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _script_examples(script: dict[str, Any]) -> list[tuple[str, str]]:
    items = script.get("items")
    if not isinstance(items, list):
        return []
    examples: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("user_prompt"), str):
            continue
        answer = item.get("teacher_correction")
        if not isinstance(answer, str) or not answer.strip():
            expected_key = (
                "expected_after_correction"
                if item.get("ask_after_correction") is True
                else "expected_original"
            )
            expected = item.get(expected_key)
            acceptable = (
                expected.get("acceptable")
                if isinstance(expected, dict)
                else None
            )
            answer = next(
                (
                    value
                    for value in acceptable or []
                    if isinstance(value, str) and value.strip()
                ),
                None,
            )
        if isinstance(answer, str) and answer.strip():
            examples.append((item["user_prompt"], answer))
    return examples


def _surface_words(value: str) -> list[str]:
    return [match.group(0) for match in _SURFACE_WORD.finditer(value)]


def _language(prompt: str, response: str) -> str:
    text = f"{prompt}\n{response}"
    if _JAPANESE.search(text):
        return "japanese"
    words = {word.casefold() for word in _surface_words(text)}
    if len(words & _GERMAN_MARKERS) >= 2 or any(
        character in text.casefold() for character in "äöüß"
    ):
        return "german"
    return "english"


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
