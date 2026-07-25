from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_SCHEMA = "ninereeds_cortex_development_state_v1"
POLICY_SCHEMA = "ninereeds_cortex_development_policy_v1"
FULL_CORE_PARAMETER_FLOOR = 1_000_000_000


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
        reports = self._reports()
        blocks: list[dict[str, Any]] = []
        evaluations: list[dict[str, Any]] = []
        for report in reports:
            result = report.get("result")
            if not isinstance(result, dict) or result.get("status") != "completed":
                continue
            if result.get("kind") == "cortex_block":
                blocks.append(report)
            elif result.get("kind") == "cortex_evaluation":
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
        total_steps = full_core_steps = bridge_steps = examples_seen = 0
        full_core_blocks = bridge_blocks = 0
        architecture = policy["architecture"]
        for report in blocks:
            result = report["result"]
            checkpoint = _string_or_none(result.get("checkpoint_after"))
            if checkpoint is None or (lineage and checkpoint not in lineage):
                continue
            metadata = result.get("metadata")
            if not isinstance(metadata, dict):
                continue
            architecture = str(metadata.get("architecture") or architecture)
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
                "Accumulate broad, diverse full-core MSM bootstrap steps from the current "
                "developmental checkpoint; do not substitute a bridge-only concept repair."
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
        return {
            "schema_version": STATE_SCHEMA,
            "architecture": architecture,
            "components": {
                "ingress": {
                    "model": "multilingual BERT",
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
                "policy_path": _display_path(self.policy_path, self.repo_root),
                "report_count": len(reports),
            },
            "updated_at": utc_now(),
        }

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


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
