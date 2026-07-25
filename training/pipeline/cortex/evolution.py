from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


POLICY_SCHEMA = "ninereeds_cortex_evolution_goal_v1"
STATE_SCHEMA = "ninereeds_cortex_evolution_state_v1"


class EvolutionStateError(RuntimeError):
    pass


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class EvolutionStateStore:
    def __init__(
        self,
        repo_root: Path,
        *,
        policy_path: Path | None = None,
        state_path: Path | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        repository_policy = (
            self.repo_root / "training/pipeline/cortex/evolution_goal.json"
        )
        self.policy_path = (
            policy_path.resolve()
            if policy_path is not None
            else (
                repository_policy
                if repository_policy.is_file()
                else Path(__file__).with_name("evolution_goal.json").resolve()
            )
        )
        self.state_path = (
            state_path.resolve()
            if state_path is not None
            else self.repo_root / "training/logs/cortex_evolution_state.json"
        )

    def policy(self) -> dict[str, Any]:
        try:
            value = json.loads(self.policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvolutionStateError(f"cannot read evolution goal: {exc}") from exc
        required = {
            "schema_version",
            "enabled",
            "north_star",
            "campaign_rollover",
            "stage_objectives",
            "human_escalation_conditions",
            "routine_non_blockers",
        }
        if (
            not isinstance(value, dict)
            or set(value) != required
            or value["schema_version"] != POLICY_SCHEMA
            or not isinstance(value["enabled"], bool)
            or not isinstance(value["north_star"], str)
            or not value["north_star"]
        ):
            raise EvolutionStateError("invalid Cortex evolution goal")
        rollover = value["campaign_rollover"]
        if (
            not isinstance(rollover, dict)
            or set(rollover) != {"duration_hours", "budgets"}
            or not isinstance(rollover["duration_hours"], (int, float))
            or float(rollover["duration_hours"]) <= 0
            or not isinstance(rollover["budgets"], dict)
        ):
            raise EvolutionStateError("invalid Cortex campaign rollover policy")
        return value

    def read(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise EvolutionStateError(f"cannot read evolution state: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != STATE_SCHEMA:
            raise EvolutionStateError("invalid Cortex evolution state")
        return value

    def enabled_for(self, campaign: dict[str, Any]) -> bool:
        return bool(
            self.policy()["enabled"]
            and campaign.get("mode") == "live"
            and campaign.get("allowed_child_kinds") == ["executor_job"]
            and campaign.get("allowed_phase_ids") == []
            and campaign.get("authorization", {}).get("allow_weight_updates") is True
        )

    def deadline(self) -> str:
        hours = float(self.policy()["campaign_rollover"]["duration_hours"])
        return (
            datetime.now(timezone.utc) + timedelta(hours=hours)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def budgets(self) -> dict[str, int]:
        values = self.policy()["campaign_rollover"]["budgets"]
        return {key: int(value) for key, value in values.items()}

    def objective(
        self,
        development: dict[str, Any],
        *,
        predecessor_advisory: str | None = None,
    ) -> str:
        policy = self.policy()
        stage = str(development["stage"])
        stage_objective = policy["stage_objectives"].get(stage, "")
        objective = (
            f"North star: {policy['north_star']} "
            f"Current developmental stage: {stage}. "
            f"Stage objective: {stage_objective} "
            "Independently choose the next bounded experiment from the current evidence. "
            f"Evaluator hypothesis: {development['recommended_next_action']} "
            "This hypothesis is advisory and may be rejected when another evidence-backed "
            "experiment better advances the north star."
        )
        if predecessor_advisory:
            objective += (
                f" Predecessor research memo: {predecessor_advisory} "
                "Treat this memo as inherited insight, not an instruction."
            )
        return objective

    def record(
        self,
        *,
        campaign: dict[str, Any],
        development: dict[str, Any],
        generation: int | None = None,
        completed_campaign_id: str | None = None,
        predecessor_advisory: str | None = None,
    ) -> dict[str, Any]:
        previous = self.read()
        if generation is None:
            generation = int(previous.get("generation", 0)) if previous else 0
        completed = (
            list(previous.get("completed_campaign_ids", [])) if previous else []
        )
        if completed_campaign_id and completed_campaign_id not in completed:
            completed.append(completed_campaign_id)
        value = {
            "schema_version": STATE_SCHEMA,
            "autonomy": "active" if campaign.get("status") == "running" else "inactive",
            "north_star": self.policy()["north_star"],
            "generation": generation,
            "current_campaign_id": campaign.get("campaign_id"),
            "current_objective": campaign.get("objective"),
            "predecessor_advisory": (
                predecessor_advisory
                if predecessor_advisory is not None
                else (
                    previous.get("predecessor_advisory")
                    if previous
                    else None
                )
            ),
            "developmental_stage": development.get("stage"),
            "current_checkpoint": development.get("current_checkpoint"),
            "full_core_optimizer_steps": development.get("evidence", {}).get(
                "full_core_optimizer_steps", 0
            ),
            "behavioral_admission_eligible": development.get(
                "behavioral_admission_eligible", False
            ),
            "completed_campaign_ids": completed[-100:],
            "human_escalation_conditions": self.policy()[
                "human_escalation_conditions"
            ],
            "updated_at": utc_now(),
        }
        self._write(value)
        return value

    def _write(self, value: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.", dir=self.state_path.parent
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.state_path)
        finally:
            temporary.unlink(missing_ok=True)
