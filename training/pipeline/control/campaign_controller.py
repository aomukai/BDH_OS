from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab.backend.config import LabConfig
from lab.backend.messages.store import MessageStore
from training.pipeline.cortex.artifacts import CampaignArtifactError, CampaignRegistry
from training.pipeline.cortex.development import DevelopmentStateStore
from training.pipeline.cortex.evolution import EvolutionStateStore
from training.pipeline.cortex.foundation_corpus import (
    FOUNDATION_BLOCK_SIZE,
    build_foundation_replay_script,
    foundation_replay_chunks,
)

from .ledger import ControlLedger, LedgerError, TERMINAL_RECEIPT_STATUSES, utc_now


CAMPAIGN_SCHEMA = "ninereeds_autonomous_campaign_v1"
CAMPAIGN_STATUSES = {"running", "waiting", "paused", "completed", "blocked"}
CAMPAIGN_REGIMES = {"standard", "play"}
COUNTED_KINDS = {
    "strategic_decision": "strategic_boundaries",
    "phase_block": "phase_blocks",
    "executor_job": "executor_jobs",
    "trainer_session": "trainer_sessions",
}
ALLOWED_CHILD_KINDS = {"phase_block", "executor_job"}
ALLOWED_PHASE_IDS = {"phase_0_form", "phase_1_word_form"}
AUTHORIZATION_KEYS = {
    "allow_weight_updates",
    "allow_checkpoint_promotion",
    "allow_auto_advance",
}
STRATEGIC_BOUNDARY_INTERVAL_SECONDS = 15 * 60
MAX_CAMPAIGN_BUDGET = 1_000
PREPARED_PLAY_BLOCK_STEPS = FOUNDATION_BLOCK_SIZE
EVOLUTION_CAMPAIGN_ID = re.compile(
    r"^cortex-evolution-(?P<stage>[a-z0-9-]+)-g(?P<generation>[0-9]{4})$"
)


class CampaignError(RuntimeError):
    pass


def _parse_time(value: str) -> float:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


class CampaignStateStore:
    def __init__(self, control_root: Path) -> None:
        self.root = control_root.resolve() / "campaign"
        self.state_path = self.root / "state.json"
        self.lock_path = self.root / "campaign.lock"
        self.derivation_failures_dir = self.root / "derivation_failures"
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.derivation_failures_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    def read(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignError(f"cannot read campaign state: {exc}") from exc
        if isinstance(value, dict) and "regime" not in value and "play" not in value:
            value = {**value, "regime": "standard", "play": None}
        if isinstance(value, dict) and "governance" not in value:
            value = {
                **value,
                "governance": {
                    "pending_directive": None,
                    "last_review_id": None,
                    "last_reviewed_mutations": 0,
                },
            }
        self.validate(value)
        return value

    def write(self, state: dict[str, Any]) -> None:
        self.validate(state)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            dir=self.root,
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(self.state_path)
        finally:
            temporary.unlink(missing_ok=True)

    def locked(self):
        self.lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return self.lock_path.open("a+", encoding="utf-8")

    def derivation_failure(self, plan_id: str) -> dict[str, Any] | None:
        path = self._derivation_failure_path(plan_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignError(f"cannot read derivation failure: {exc}") from exc
        expected = {"plan_id", "error_type", "message", "observed_at"}
        if (
            not isinstance(value, dict)
            or set(value) != expected
            or value["plan_id"] != plan_id
            or not all(
                isinstance(value[key], str) and value[key]
                for key in ("error_type", "message", "observed_at")
            )
        ):
            raise CampaignError(f"invalid derivation failure: {plan_id}")
        _parse_time(value["observed_at"])
        return value

    def record_derivation_failure(
        self,
        plan_id: str,
        error: BaseException,
    ) -> dict[str, Any]:
        existing = self.derivation_failure(plan_id)
        if existing is not None:
            return existing
        value = {
            "plan_id": plan_id,
            "error_type": type(error).__name__,
            "message": str(error)[:4000] or type(error).__name__,
            "observed_at": utc_now(),
        }
        path = self._derivation_failure_path(plan_id)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return value

    def _derivation_failure_path(self, plan_id: str) -> Path:
        if re.fullmatch(r"[A-Za-z0-9._-]{1,200}", plan_id) is None:
            raise CampaignError("invalid derivation failure plan_id")
        return self.derivation_failures_dir / f"{plan_id}.json"

    @staticmethod
    def validate(state: Any) -> None:
        expected = {
            "schema_version",
            "campaign_id",
            "status",
            "mode",
            "objective",
            "created_at",
            "updated_at",
            "deadline_at",
            "seed_plan_id",
            "root_boundary_plan_id",
            "current_plan_id",
            "boundary_index",
            "authorization",
            "allowed_child_kinds",
            "allowed_phase_ids",
            "context_files",
            "budgets",
            "usage",
            "stop_reason",
            "history",
            "regime",
            "play",
            "governance",
        }
        if not isinstance(state, dict) or set(state) != expected:
            raise CampaignError("campaign state fields do not match v1")
        if state["schema_version"] != CAMPAIGN_SCHEMA:
            raise CampaignError("invalid campaign schema_version")
        if state["regime"] not in CAMPAIGN_REGIMES:
            raise CampaignError("invalid campaign regime")
        CampaignStateStore._validate_play(state["regime"], state["play"])
        governance = state["governance"]
        if (
            not isinstance(governance, dict)
            or set(governance)
            != {"pending_directive", "last_review_id", "last_reviewed_mutations"}
            or governance["pending_directive"] is not None
            and not isinstance(governance["pending_directive"], str)
            or governance["last_review_id"] is not None
            and not isinstance(governance["last_review_id"], str)
            or isinstance(governance["last_reviewed_mutations"], bool)
            or not isinstance(governance["last_reviewed_mutations"], int)
            or governance["last_reviewed_mutations"] < 0
        ):
            raise CampaignError("campaign governance state is invalid")
        if (
            not isinstance(state["campaign_id"], str)
            or re.fullmatch(r"[A-Za-z0-9._-]{1,80}", state["campaign_id"]) is None
        ):
            raise CampaignError("invalid campaign_id")
        if state["status"] not in CAMPAIGN_STATUSES:
            raise CampaignError("invalid campaign status")
        if state["mode"] not in {"shadow", "live"}:
            raise CampaignError("invalid campaign mode")
        for key in ("objective", "created_at", "updated_at", "deadline_at", "seed_plan_id", "current_plan_id"):
            if not isinstance(state[key], str) or not state[key]:
                raise CampaignError(f"{key} must be a non-empty string")
        _parse_time(state["created_at"])
        _parse_time(state["updated_at"])
        _parse_time(state["deadline_at"])
        root = state["root_boundary_plan_id"]
        if root is not None and (not isinstance(root, str) or not root):
            raise CampaignError("root_boundary_plan_id must be a string or null")
        if (
            isinstance(state["boundary_index"], bool)
            or not isinstance(state["boundary_index"], int)
            or state["boundary_index"] < 0
        ):
            raise CampaignError("boundary_index must be a non-negative integer")
        authorization = state["authorization"]
        if (
            not isinstance(authorization, dict)
            or set(authorization) != AUTHORIZATION_KEYS
            or not all(isinstance(value, bool) for value in authorization.values())
        ):
            raise CampaignError("campaign authorization is invalid")
        if state["mode"] == "shadow" and any(authorization.values()):
            raise CampaignError("shadow campaign cannot authorize mutations")
        if authorization["allow_checkpoint_promotion"]:
            raise CampaignError("autonomous campaign cannot authorize checkpoint promotion")
        kinds = state["allowed_child_kinds"]
        if (
            not isinstance(kinds, list)
            or not kinds
            or len(set(kinds)) != len(kinds)
            or not all(kind in ALLOWED_CHILD_KINDS for kind in kinds)
        ):
            raise CampaignError("allowed_child_kinds are invalid")
        phases = state["allowed_phase_ids"]
        if (
            not isinstance(phases, list)
            or len(set(phases)) != len(phases)
            or not all(phase in ALLOWED_PHASE_IDS for phase in phases)
        ):
            raise CampaignError("allowed_phase_ids are invalid")
        contexts = state["context_files"]
        if (
            not isinstance(contexts, list)
            or len(contexts) > 32
            or len(set(contexts)) != len(contexts)
            or not all(isinstance(path, str) and path for path in contexts)
        ):
            raise CampaignError("context_files are invalid")
        budget_keys = set(COUNTED_KINDS.values())
        for name in ("budgets", "usage"):
            values = state[name]
            if (
                not isinstance(values, dict)
                or set(values) != budget_keys
                or not all(
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and value >= 0
                    for value in values.values()
                )
            ):
                raise CampaignError(f"{name} are invalid")
        if not 1 <= state["budgets"]["strategic_boundaries"] <= MAX_CAMPAIGN_BUDGET:
            raise CampaignError(
                "strategic boundary budget must be from 1 through "
                f"{MAX_CAMPAIGN_BUDGET}"
            )
        if any(value > MAX_CAMPAIGN_BUDGET for value in state["budgets"].values()):
            raise CampaignError(
                f"campaign budget may not exceed {MAX_CAMPAIGN_BUDGET}"
            )
        if state["stop_reason"] is not None and not isinstance(state["stop_reason"], str):
            raise CampaignError("stop_reason must be a string or null")
        history = state["history"]
        if not isinstance(history, list) or len(history) > 100:
            raise CampaignError("campaign history is invalid")

    @staticmethod
    def _validate_play(regime: str, play: Any) -> None:
        if regime == "standard":
            if play is not None:
                raise CampaignError("standard campaign cannot carry Play state")
            return
        expected = {
            "baseline_checkpoint",
            "target_score",
            "branch_target_steps",
            "max_branches",
            "active_branch",
            "completed_branches",
            "best_checkpoint",
            "best_score",
        }
        if not isinstance(play, dict) or set(play) != expected:
            raise CampaignError("Play campaign fields do not match v1")
        if not isinstance(play["baseline_checkpoint"], str) or not play["baseline_checkpoint"]:
            raise CampaignError("Play baseline_checkpoint is invalid")
        if not isinstance(play["target_score"], (int, float)) or isinstance(play["target_score"], bool) or not 0 < float(play["target_score"]) <= 1:
            raise CampaignError("Play target_score is invalid")
        for key in ("branch_target_steps", "max_branches"):
            value = play[key]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100_000:
                raise CampaignError(f"Play {key} is invalid")
        if not isinstance(play["completed_branches"], list) or len(play["completed_branches"]) > play["max_branches"]:
            raise CampaignError("Play completed_branches are invalid")
        if play["best_checkpoint"] is not None and not isinstance(play["best_checkpoint"], str):
            raise CampaignError("Play best_checkpoint is invalid")
        if not isinstance(play["best_score"], (int, float)) or isinstance(play["best_score"], bool) or not 0 <= float(play["best_score"]) <= 1:
            raise CampaignError("Play best_score is invalid")
        branch = play["active_branch"]
        branch_expected = {
            "branch_id",
            "branch_index",
            "strategy",
            "current_checkpoint",
            "optimizer_steps",
            "evaluation_plan_ids",
        }
        if not isinstance(branch, dict) or set(branch) != branch_expected:
            raise CampaignError("Play active_branch fields do not match v1")
        if not isinstance(branch["branch_id"], str) or not branch["branch_id"]:
            raise CampaignError("Play branch_id is invalid")
        if isinstance(branch["branch_index"], bool) or not isinstance(branch["branch_index"], int) or branch["branch_index"] < 1:
            raise CampaignError("Play branch_index is invalid")
        if branch["strategy"] is not None and not isinstance(branch["strategy"], str):
            raise CampaignError("Play strategy is invalid")
        if not isinstance(branch["current_checkpoint"], str) or not branch["current_checkpoint"]:
            raise CampaignError("Play current_checkpoint is invalid")
        if isinstance(branch["optimizer_steps"], bool) or not isinstance(branch["optimizer_steps"], int) or branch["optimizer_steps"] < 0:
            raise CampaignError("Play optimizer_steps is invalid")
        ids = branch["evaluation_plan_ids"]
        if not isinstance(ids, list) or len(set(ids)) != len(ids) or not all(isinstance(value, str) and value for value in ids):
            raise CampaignError("Play evaluation_plan_ids are invalid")


class CampaignController:
    def __init__(
        self,
        ledger: ControlLedger,
        *,
        repo_root: Path,
        store: CampaignStateStore | None = None,
        message_store: MessageStore | None = None,
        controller_id: str = "campaign-controller",
        strategic_boundary_interval_seconds: int = STRATEGIC_BOUNDARY_INTERVAL_SECONDS,
    ) -> None:
        self.ledger = ledger
        self.repo_root = repo_root.resolve()
        self.store = store or CampaignStateStore(ledger.root)
        self.message_store = message_store or MessageStore(LabConfig.from_env())
        self.controller_id = controller_id
        if (
            isinstance(strategic_boundary_interval_seconds, bool)
            or not isinstance(strategic_boundary_interval_seconds, int)
            or strategic_boundary_interval_seconds < 0
        ):
            raise CampaignError(
                "strategic_boundary_interval_seconds must be non-negative"
            )
        self.strategic_boundary_interval_seconds = strategic_boundary_interval_seconds
        self.development_store = DevelopmentStateStore(
            self.repo_root, reports_dir=self.ledger.reports_dir
        )
        self.evolution_store = EvolutionStateStore(self.repo_root)

    def start(
        self,
        *,
        campaign_id: str,
        mode: str,
        objective: str,
        seed_plan_id: str,
        deadline_at: str,
        authorization: dict[str, bool],
        allowed_child_kinds: list[str],
        allowed_phase_ids: list[str],
        context_files: list[str],
        budgets: dict[str, int],
        regime: str = "standard",
        play: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            existing = self.store.read()
            if existing is not None and existing["status"] in {"running", "waiting", "paused"}:
                raise CampaignError(
                    f"campaign {existing['campaign_id']} is still {existing['status']}"
                )
            plan = self.ledger.plan(seed_plan_id)
            receipt = self.ledger.receipt(seed_plan_id)
            if plan is None or receipt is None:
                raise CampaignError("seed plan does not exist")
            if receipt["status"] not in TERMINAL_RECEIPT_STATUSES:
                raise CampaignError("seed plan is not terminal")
            for relative in context_files:
                path = (self.repo_root / relative).resolve()
                if (
                    path == self.repo_root
                    or self.repo_root not in path.parents
                    or ".git" in path.relative_to(self.repo_root).parts
                    or not path.is_file()
                ):
                    raise CampaignError(f"invalid campaign context file: {relative}")
            now = utc_now()
            try:
                CampaignRegistry(self.repo_root).get_or_allocate(
                    campaign_id=campaign_id,
                    objective=objective.strip(),
                    created_at=now,
                )
            except CampaignArtifactError as exc:
                raise CampaignError(
                    f"cannot allocate campaign number: {exc}"
                ) from exc
            play_state = None
            if regime == "play":
                if not isinstance(play, dict):
                    raise CampaignError("Play campaign requires a play configuration")
                required = {
                    "baseline_checkpoint",
                    "target_score",
                    "branch_target_steps",
                    "max_branches",
                }
                if set(play) != required:
                    raise CampaignError("Play configuration fields do not match v1")
                play_state = {
                    **play,
                    "active_branch": self._new_play_branch(
                        campaign_id,
                        1,
                        str(play["baseline_checkpoint"]),
                    ),
                    "completed_branches": [],
                    "best_checkpoint": None,
                    "best_score": 0.0,
                }
            elif regime != "standard" or play is not None:
                raise CampaignError("invalid standard campaign configuration")
            state = {
                "schema_version": CAMPAIGN_SCHEMA,
                "campaign_id": campaign_id,
                "status": "running",
                "mode": mode,
                "objective": objective.strip(),
                "created_at": now,
                "updated_at": now,
                "deadline_at": deadline_at,
                "seed_plan_id": seed_plan_id,
                "root_boundary_plan_id": None,
                "current_plan_id": seed_plan_id,
                "boundary_index": 0,
                "authorization": dict(authorization),
                "allowed_child_kinds": list(allowed_child_kinds),
                "allowed_phase_ids": list(allowed_phase_ids),
                "context_files": list(context_files),
                "budgets": dict(budgets),
                "usage": {key: 0 for key in COUNTED_KINDS.values()},
                "stop_reason": None,
                "history": [
                    {
                        "at": now,
                        "status": "running",
                        "detail": f"Campaign started from terminal seed {seed_plan_id}.",
                    }
                ],
                "regime": regime,
                "play": play_state,
                "governance": {
                    "pending_directive": None,
                    "last_review_id": None,
                    "last_reviewed_mutations": 0,
                },
            }
            self.store.write(state)
            if (
                self.evolution_store.enabled_for(state)
                and not self._uses_prepared_allowlist_wave(state)
            ):
                self.evolution_store.record(
                    campaign=state,
                    development=self.development_store.reconcile(),
                )
        self.message_store.write_system_notice(
            f"campaign-started:{campaign_id}",
            f"Autonomous campaign started: {campaign_id}",
            (
                f"The campaign is running from {seed_plan_id}. It may create at most "
                f"{budgets['strategic_boundaries']} strategic boundaries and "
                f"{budgets['phase_blocks']} phase blocks before pausing."
            ),
            metadata={"campaign_id": campaign_id},
        )
        return state

    @staticmethod
    def _new_play_branch(
        campaign_id: str,
        branch_index: int,
        baseline_checkpoint: str,
    ) -> dict[str, Any]:
        return {
            "branch_id": f"{campaign_id}-play-{branch_index:03d}",
            "branch_index": branch_index,
            "strategy": None,
            "current_checkpoint": baseline_checkpoint,
            "optimizer_steps": 0,
            "evaluation_plan_ids": [],
        }

    @staticmethod
    def _prepared_play_block_steps(state: dict[str, Any]) -> int | None:
        if state.get("regime") != "play":
            return None
        context_files = state.get("context_files")
        if not isinstance(context_files, list):
            return None
        if any(
            isinstance(relative, str)
            and relative.startswith("training/pipeline/cortex/allowlist_waves/")
            and re.search(r"/block-[0-9]{2}\.jsonl$", relative)
            for relative in context_files
        ):
            return PREPARED_PLAY_BLOCK_STEPS
        return None

    def _play_campaign_snapshot(self, state: dict[str, Any]) -> dict[str, Any] | None:
        if state.get("regime") != "play":
            return None
        play = state["play"]
        branch = play["active_branch"]
        required_steps = self._prepared_play_block_steps(state)
        remaining_steps = max(
            0,
            int(play["branch_target_steps"]) - int(branch["optimizer_steps"]),
        )
        snapshot = {
            "baseline_checkpoint": play["baseline_checkpoint"],
            "branch_id": branch["branch_id"],
            "branch_index": branch["branch_index"],
            "current_checkpoint": branch["current_checkpoint"],
            "optimizer_steps": branch["optimizer_steps"],
            "target_steps": play["branch_target_steps"],
            "remaining_steps": remaining_steps,
            "target_score": play["target_score"],
            "completed_branches": len(play["completed_branches"]),
            "max_branches": play["max_branches"],
            "best_score": play["best_score"],
            "required_block_steps": int(required_steps or 0),
            "can_accept_full_block": True
            if required_steps is None
            else remaining_steps >= required_steps,
        }
        return snapshot

    def _latest_play_branch_observation(
        self,
        branch: dict[str, Any],
    ) -> dict[str, Any]:
        for plan_id in reversed(branch["evaluation_plan_ids"]):
            report = self.ledger.report(plan_id)
            result = report.get("result") if isinstance(report, dict) else None
            certificate = result.get("certificate") if isinstance(result, dict) else None
            if isinstance(certificate, dict):
                return {
                    "score": float(certificate.get("overall_score") or 0.0),
                    "failure_modes": list(certificate.get("failure_modes") or []),
                    "insights": list(
                        certificate.get("diagnostic_findings")
                        or certificate.get("reasons")
                        or []
                    ),
                    "representation_drift": copy.deepcopy(
                        certificate.get("representation_drift") or {}
                    ),
                }
        return {
            "score": 0.0,
            "failure_modes": [],
            "insights": [],
            "representation_drift": {},
        }

    def _start_next_play_branch(
        self,
        state: dict[str, Any],
        *,
        status: str,
        reason: str,
    ) -> bool:
        play = state.get("play")
        if state.get("regime") != "play" or not isinstance(play, dict):
            return False
        if len(play["completed_branches"]) >= int(play["max_branches"]):
            return False
        branch = play["active_branch"]
        observation = self._latest_play_branch_observation(branch)
        branch_record = {
            **copy.deepcopy(branch),
            "terminal_score": observation["score"],
            "terminal_checkpoint": branch["current_checkpoint"],
            "status": status,
            "failure_modes": observation["failure_modes"],
            "insights": [reason, *observation["insights"]],
            "representation_drift": observation["representation_drift"],
            "completed_at": utc_now(),
        }
        play["completed_branches"].append(branch_record)
        next_index = len(play["completed_branches"]) + 1
        if next_index > int(play["max_branches"]):
            self._stop(
                state,
                "completed",
                (
                    f"Play research budget completed with "
                    f"{len(play['completed_branches'])} documented branches; best score "
                    f"{play['best_score']:.1%} at "
                    f"{play['best_checkpoint'] or 'no retained checkpoint'}."
                ),
                event="play-branch-budget",
            )
            return True
        play["active_branch"] = self._new_play_branch(
            state["campaign_id"],
            next_index,
            play["baseline_checkpoint"],
        )
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [{
                "at": state["updated_at"],
                "status": "running",
                "detail": (
                    f"Documented Play branch {branch_record['branch_id']} as "
                    f"{status}; starting branch {next_index} from preserved baseline "
                    f"{play['baseline_checkpoint']}. {reason}"
                ),
            }]
        )[-100:]
        return True

    def _maybe_start_next_play_branch_for_block_capacity(
        self,
        state: dict[str, Any],
    ) -> bool:
        play = state.get("play")
        if state.get("regime") != "play" or not isinstance(play, dict):
            return False
        required_steps = self._prepared_play_block_steps(state)
        if required_steps is None:
            return False
        branch = play["active_branch"]
        remaining_steps = int(play["branch_target_steps"]) - int(branch["optimizer_steps"])
        if remaining_steps >= required_steps:
            return False
        return self._start_next_play_branch(
            state,
            status="completed_full_block_horizon",
            reason=(
                f"The active branch has only {max(0, remaining_steps)} optimizer "
                f"steps remaining, but the prepared curriculum block requires exactly "
                f"{required_steps} examples/steps. Rolling to the next independent "
                "baseline branch prevents another AUTHORITY_REQUIRED deadlock."
            ),
        )

    def reconcile(self) -> dict[str, Any]:
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                return {"active": False, "action": "none"}
            if state["status"] != "running":
                if state["status"] == "blocked" and self._blocked_provider_capacity_recovered(state):
                    state["status"] = "running"
                    state["stop_reason"] = None
                    state["updated_at"] = utc_now()
                    state["history"] = (
                        state["history"]
                        + [
                            {
                                "at": state["updated_at"],
                                "status": "running",
                                "detail": (
                                    "Provider capacity recovered after a blocked strategic "
                                    "boundary; retrying from a fresh boundary."
                                ),
                            }
                        ]
                    )[-100:]
                    self.store.write(state)
                else:
                    return {
                        "active": False,
                        "action": "none",
                        "status": state["status"],
                    }
            evolutionary = (
                self.evolution_store.enabled_for(state)
                and not self._uses_prepared_allowlist_wave(state)
            )
            development_state = self.development_store.reconcile()
            if (
                evolutionary
                and development_state.get("stage") == "foundational_bootstrap"
            ):
                current_objective = self.evolution_store.objective(development_state)
                if state["objective"] != current_objective:
                    state["objective"] = current_objective
                    state["updated_at"] = utc_now()
                    state["history"] = (
                        state["history"]
                        + [
                            {
                                "at": state["updated_at"],
                                "status": "running",
                                "detail": (
                                    "Refreshed the active campaign objective from the "
                                    "operator-directed foundational replay policy; retired "
                                    "the superseded predecessor micro-block advisory."
                                ),
                            }
                        ]
                    )[-100:]
                    self.store.write(state)
            if evolutionary:
                self.evolution_store.record(
                    campaign=state,
                    development=development_state,
                    predecessor_advisory=(
                        ""
                        if development_state.get("stage")
                        == "foundational_bootstrap"
                        else None
                    ),
                )
            deadline_reached = time.time() >= _parse_time(state["deadline_at"])

            plans = self._plans()
            current = state["current_plan_id"]
            if current not in plans:
                self._stop(
                    state,
                    "blocked",
                    f"Current plan disappeared from the ledger: {current}",
                    event="missing-plan",
                )
                return {"active": False, "action": "blocked_missing_plan"}

            children = self._children(plans)
            while state["root_boundary_plan_id"] is not None and children.get(current):
                descendants = children[current]
                if len(descendants) != 1:
                    self._stop(
                        state,
                        "blocked",
                        f"Plan {current} has {len(descendants)} children; expected at most one.",
                        event="branching",
                    )
                    return {"active": False, "action": "blocked_branching"}
                current = descendants[0]["plan_id"]
                state["current_plan_id"] = current

            usage = self._usage(state, plans)
            state["usage"] = usage
            receipt = self.ledger.receipt(current)
            if receipt is None:
                self._stop(
                    state,
                    "blocked",
                    f"Current plan has no receipt: {current}",
                    event="missing-receipt",
                )
                return {"active": False, "action": "blocked_missing_receipt"}
            if receipt["status"] not in TERMINAL_RECEIPT_STATUSES:
                if deadline_reached and not evolutionary:
                    self._stop(
                        state,
                        "paused",
                        "Campaign wall-clock deadline reached while work was still active.",
                        event="deadline-active",
                    )
                    return {"active": False, "action": "paused_deadline"}
                state["updated_at"] = utc_now()
                self.store.write(state)
                return {
                    "active": True,
                    "action": "waiting_for_plan",
                    "plan_id": current,
                    "plan_status": receipt["status"],
                }

            plan = plans[current]
            report = self.ledger.report(current)
            play_result = self._reconcile_play_evaluation(
                state,
                plan=plan,
                report=report,
                plans=plans,
            )
            if play_result is not None:
                return play_result
            if plan["kind"] == "strategic_decision":
                decision = (report or {}).get("result", {}).get("decision")
                action = decision.get("action") if isinstance(decision, dict) else None
                if action in {"wait", "request_human"}:
                    routine_review = (
                        evolutionary
                        and plan.get("payload", {}).get("allowed_child_kinds") == []
                    )
                    if evolutionary and (action == "wait" or routine_review):
                        return self._rollover(
                            state,
                            seed_plan_id=current,
                            reason=(
                                "Routine strategic wait/review completed; autonomous "
                                "evolution continued in a fresh bounded campaign."
                            ),
                        )
                    reason = (
                        decision.get("user_message")
                        if action == "request_human"
                        else decision.get("rationale")
                    )
                    self._stop(
                        state,
                        "waiting",
                        str(reason or f"Strategic decision returned {action}."),
                        event=f"strategic-{action}",
                    )
                    return {"active": False, "action": f"waiting_{action}"}
                if receipt["status"] != "completed":
                    if (
                        self._strategic_provider_capacity_block(receipt, report)
                        and self._provider_capacity_available()
                        and not deadline_reached
                    ):
                        return self._create_strategic_provider_retry(
                            state,
                            failed_plan_id=current,
                        )
                    if (
                        self._repairable_strategic_context_failure(receipt)
                        and not deadline_reached
                    ):
                        return self._create_strategic_context_repair(
                            state,
                            failed_plan_id=current,
                            error=str(receipt.get("last_error") or ""),
                        )
                    self._stop(
                        state,
                        "blocked",
                        f"Strategic boundary ended {receipt['status']} without a child.",
                        event="strategic-blocked",
                    )
                    return {"active": False, "action": "blocked_strategic"}
                self._stop(
                    state,
                    "blocked",
                    "Strategic boundary completed with enqueue_plan but no child appeared.",
                    event="missing-strategic-child",
                )
                return {"active": False, "action": "blocked_missing_child"}

            if (
                plan["kind"] == "cortex_block"
                and receipt["status"] in {"blocked", "dead_letter"}
                and not deadline_reached
            ):
                technical_retry = self._create_prepared_wave_technical_retry(
                    state,
                    failed_plan=plan,
                    receipt=receipt,
                    plans=plans,
                )
                if technical_retry is not None:
                    return technical_retry

            if self._objective_complete(plan, report):
                self._stop(
                    state,
                    "completed",
                    f"Objective gate met by {current}.",
                    event="objective-complete",
                )
                return {"active": False, "action": "completed"}

            if (
                not deadline_reached
                and state["mode"] == "live"
                and state["authorization"]["allow_weight_updates"]
                and plan["kind"] == "cortex_evaluation"
                and receipt["status"] == "completed"
                and development_state.get("stage") == "foundational_bootstrap"
                and not self._uses_prepared_allowlist_wave(state)
            ):
                result = report.get("result") if isinstance(report, dict) else None
                parent_checkpoint = (
                    result.get("checkpoint_after")
                    if isinstance(result, dict)
                    else None
                )
                if isinstance(parent_checkpoint, str) and parent_checkpoint:
                    return self._create_foundational_replay_block(
                        state,
                        parent_plan_id=current,
                        parent_checkpoint=parent_checkpoint,
                        plans=plans,
                    )

            derivation_failure = None
            workflow = plan["payload"].get("workflow")
            if (
                plan["kind"] == "executor_job"
                and isinstance(workflow, dict)
                and workflow.get("type") in {"cortex_train", "cortex_curriculum"}
                and (
                    state["root_boundary_plan_id"] is None
                    or not children.get(current)
                )
            ):
                derivation_failure = self.store.derivation_failure(current) or {
                    "plan_id": current,
                    "error_type": "MissingDerivedChild",
                    "message": (
                        "The terminal Cortex executor job has no deterministic "
                        "cortex_block child."
                    ),
                    "observed_at": utc_now(),
                }

            remaining = {
                key: state["budgets"][key] - usage[key]
                for key in state["budgets"]
            }
            if self._maybe_start_next_play_branch_for_block_capacity(state):
                if state["status"] != "running":
                    return {"active": False, "action": "completed_play_budget"}
                state["usage"] = usage
            child_budget_available = any(
                remaining.get(COUNTED_KINDS[kind], 0) > 0
                for kind in state["allowed_child_kinds"]
            )
            if (
                remaining["strategic_boundaries"] <= 0
                or not child_budget_available
            ):
                return self._await_sol_budget_review(state, usage=usage)
            wait_seconds = self._strategic_boundary_wait_seconds(state)
            if wait_seconds > 0:
                state["updated_at"] = utc_now()
                self.store.write(state)
                return {
                    "active": True,
                    "action": "waiting_for_orchestrator_window",
                    "plan_id": current,
                    "plan_status": receipt["status"],
                    "next_attempt_in_seconds": wait_seconds,
                    "cadence_seconds": self.strategic_boundary_interval_seconds,
                }
            allowed = (
                []
                if deadline_reached
                else [
                    kind
                    for kind in state["allowed_child_kinds"]
                    if remaining[COUNTED_KINDS[kind]] > 0
                ]
            )
            review_only = deadline_reached or not allowed
            boundary_index = state["boundary_index"] + 1
            boundary_id = f"{state['campaign_id']}-b{boundary_index:04d}"
            plan_id = f"plan-campaign-{boundary_id}"
            strategic = self.ledger.plan(plan_id)
            if strategic is not None and not self._existing_boundary_belongs_to_campaign(
                strategic,
                state=state,
                parent_plan_id=current,
                boundary_index=boundary_index,
            ):
                if evolutionary and self._identity_repair_is_safe(state):
                    state = self._repair_evolution_identity(
                        state,
                        collision_plan_id=plan_id,
                        development_state=development_state,
                    )
                    boundary_id = f"{state['campaign_id']}-b{boundary_index:04d}"
                    plan_id = f"plan-campaign-{boundary_id}"
                    strategic = self.ledger.plan(plan_id)
                else:
                    self._stop(
                        state,
                        "blocked",
                        (
                            f"Strategic boundary identity collides with an unrelated "
                            f"immutable plan: {plan_id}"
                        ),
                        event="boundary-identity-collision",
                    )
                    return {
                        "active": False,
                        "action": "blocked_boundary_identity_collision",
                        "plan_id": plan_id,
                    }
            if strategic is not None and not self._existing_boundary_belongs_to_campaign(
                strategic,
                state=state,
                parent_plan_id=current,
                boundary_index=boundary_index,
            ):
                self._stop(
                    state,
                    "blocked",
                    (
                        "Automatic campaign identity repair could not allocate a "
                        f"collision-free boundary: {plan_id}"
                    ),
                    event="boundary-identity-repair-failed",
                )
                return {
                    "active": False,
                    "action": "blocked_boundary_identity_repair",
                    "plan_id": plan_id,
                }
            campaign = {
                "campaign_id": state["campaign_id"],
                "boundary_index": boundary_index,
                "constraints": {
                    "remaining_phase_blocks": max(0, remaining["phase_blocks"]),
                    "remaining_executor_jobs": max(0, remaining["executor_jobs"]),
                    "remaining_trainer_sessions": max(0, remaining["trainer_sessions"]),
                    "allowed_phase_ids": state["allowed_phase_ids"],
                    "max_phase_continuation_blocks": 0,
                    "max_auto_sessions": 0,
                },
            }
            if state.get("regime") == "play":
                campaign["play"] = self._play_campaign_snapshot(state)
            if strategic is None:
                strategic = self.ledger.create_plan(
                    kind="strategic_decision",
                    mode=state["mode"],
                    payload={
                        "boundary_id": boundary_id,
                        "title": (
                            f"{state['campaign_id']} boundary {boundary_index}: choose next action"
                        ),
                        "instructions": self._instructions(
                            state,
                            current,
                            remaining,
                            derivation_failure,
                            development_state=self.development_store.reconcile(),
                            review_only=review_only,
                        ),
                        "context_files": (
                            self._review_context_files(state)
                            if review_only
                            else state["context_files"]
                        ),
                        "allowed_child_kinds": allowed,
                        "campaign": campaign,
                    },
                    created_by=self.controller_id,
                    parent_plan_id=current,
                    plan_id=plan_id,
                    authorization=state["authorization"],
                )
            state["boundary_index"] = boundary_index
            state["current_plan_id"] = strategic["plan_id"]
            if state["governance"]["pending_directive"] is not None:
                state["governance"]["pending_directive"] = None
            if state["root_boundary_plan_id"] is None:
                state["root_boundary_plan_id"] = strategic["plan_id"]
            state["usage"] = self._usage(state, self._plans())
            state["updated_at"] = utc_now()
            state["history"] = (
                state["history"]
                + [
                    {
                        "at": state["updated_at"],
                        "status": "running",
                        "detail": (
                            (
                                f"Created repair strategic boundary {strategic['plan_id']} "
                                f"after Cortex derivation failure on {current}."
                                if derivation_failure is not None
                                else (
                                    (
                                        f"Created final campaign-review boundary "
                                        f"{strategic['plan_id']} after {current}."
                                        if review_only
                                        else (
                                            f"Created strategic boundary {strategic['plan_id']} "
                                            f"after {current}."
                                        )
                                    )
                                )
                            )
                        ),
                    }
                ]
            )[-100:]
            self.store.write(state)
            return {
                "active": True,
                "action": (
                    "created_campaign_review"
                    if review_only
                    else "created_strategic_boundary"
                ),
                "plan_id": strategic["plan_id"],
            }

    def _reconcile_play_evaluation(
        self,
        state: dict[str, Any],
        *,
        plan: dict[str, Any],
        report: dict[str, Any] | None,
        plans: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        play = state.get("play")
        if state.get("regime") != "play" or not isinstance(play, dict):
            return None
        if plan["kind"] != "cortex_evaluation" or report is None:
            return None
        result = report.get("result")
        certificate = result.get("certificate") if isinstance(result, dict) else None
        if not isinstance(certificate, dict):
            return None
        # A Play campaign may be seeded by a terminal evaluation from an older
        # regime. Only evaluations explicitly produced under Play belong to the
        # active experimental lineage.
        if certificate.get("development_stage") != "play":
            return None
        branch = play["active_branch"]
        if plan["plan_id"] in branch["evaluation_plan_ids"]:
            return None
        block_id = plan.get("parent_plan_id")
        block_report = self.ledger.report(block_id) if isinstance(block_id, str) else None
        metadata = (
            block_report.get("result", {}).get("metadata")
            if isinstance(block_report, dict)
            else None
        )
        if not isinstance(metadata, dict):
            raise CampaignError("Play evaluation lacks its Cortex training metadata")
        losses = metadata.get("step_losses")
        if isinstance(losses, list):
            steps = len(losses)
        else:
            examples = int(metadata.get("examples") or 0)
            epochs = max(int(metadata.get("epochs") or 1), 1)
            batch = max(int(metadata.get("batch_size") or 1), 1)
            steps = (examples * epochs + batch - 1) // batch
        candidate = certificate.get("candidate_checkpoint")
        if not isinstance(candidate, str) or not candidate:
            raise CampaignError("Play evaluation lacks a candidate checkpoint")
        score = float(certificate.get("overall_score") or 0.0)
        branch["evaluation_plan_ids"].append(plan["plan_id"])
        branch["optimizer_steps"] += max(steps, 0)
        branch["current_checkpoint"] = candidate
        if branch["strategy"] is None and isinstance(block_id, str):
            block_plan = plans.get(block_id)
            executor = (
                plans.get(block_plan.get("parent_plan_id"))
                if isinstance(block_plan, dict)
                and isinstance(block_plan.get("parent_plan_id"), str)
                else None
            )
            task = executor.get("payload", {}).get("task") if isinstance(executor, dict) else None
            branch["strategy"] = (
                str(task.get("title"))[:500]
                if isinstance(task, dict) and task.get("title")
                else "Strategy recorded in the branch plan lineage."
            )
        if score > float(play["best_score"]):
            play["best_score"] = score
            play["best_checkpoint"] = candidate

        structural = bool(certificate.get("blocking_reasons"))
        branch_complete = (
            structural
            or score >= float(play["target_score"])
            or branch["optimizer_steps"] >= int(play["branch_target_steps"])
        )
        if not branch_complete:
            state["updated_at"] = utc_now()
            self.store.write(state)
            return None

        branch_record = {
            **copy.deepcopy(branch),
            "terminal_score": score,
            "terminal_checkpoint": candidate,
            "status": (
                "target_met"
                if score >= float(play["target_score"])
                else "structural_failure" if structural else "completed"
            ),
            "failure_modes": list(certificate.get("failure_modes") or []),
            "insights": list(
                certificate.get("diagnostic_findings")
                or certificate.get("reasons")
                or []
            ),
            "representation_drift": copy.deepcopy(
                certificate.get("representation_drift") or {}
            ),
            "completed_at": utc_now(),
        }
        play["completed_branches"].append(branch_record)
        if len(play["completed_branches"]) >= int(play["max_branches"]):
            self._stop(
                state,
                "completed",
                (
                    f"Play research budget completed with "
                    f"{len(play['completed_branches'])} documented branches; best score "
                    f"{play['best_score']:.1%} at "
                    f"{play['best_checkpoint'] or 'no retained checkpoint'}."
                ),
                event="play-branch-budget",
            )
            return {"active": False, "action": "completed_play_budget"}
        next_index = len(play["completed_branches"]) + 1
        play["active_branch"] = self._new_play_branch(
            state["campaign_id"],
            next_index,
            play["baseline_checkpoint"],
        )
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [{
                "at": state["updated_at"],
                "status": "running",
                "detail": (
                    f"Documented Play branch {branch_record['branch_id']} at "
                    f"{score:.1%}; starting branch {next_index} from the preserved baseline."
                ),
            }]
        )[-100:]
        self.store.write(state)
        return None

    def _create_foundational_replay_block(
        self,
        state: dict[str, Any],
        *,
        parent_plan_id: str,
        parent_checkpoint: str,
        plans: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        legacy_blocks = sum(
            1
            for plan in plans.values()
            if plan["kind"] == "cortex_block"
            and isinstance(plan.get("payload", {}).get("script"), dict)
            and plan["payload"]["script"].get("concept")
            == "broad_foundational_replay"
        )
        chunked_blocks = sum(
            1
            for plan in plans.values()
            if plan["kind"] == "cortex_corpus_chunk"
            and plan.get("payload", {}).get("chunk_index") == 1
            and plan.get("payload", {}).get("curriculum_id", "").startswith(
                f"{state['campaign_id']}-foundation-replay-"
            )
        )
        block_index = 1 + legacy_blocks + chunked_blocks
        session_id = (
            f"{state['campaign_id']}-foundation-replay-{block_index:04d}"
        )
        script = build_foundation_replay_script(
            self.repo_root,
            campaign_id=state["campaign_id"],
            block_index=block_index,
            parent_checkpoint=parent_checkpoint,
            orchestrator_plan_id=parent_plan_id,
        )
        chunks = foundation_replay_chunks(script)
        parent_id = parent_plan_id
        chunk_paths = []
        for chunk in chunks:
            chunk_path = (
                f"core/cortex/curricula/{session_id}/"
                f"chunk-{chunk['chunk_index']:04d}.jsonl"
            )
            chunk_paths.append(chunk_path)
            chunk_plan = self.ledger.create_plan(
                kind="cortex_corpus_chunk",
                mode="live",
                payload={
                    "curriculum_id": session_id,
                    **chunk,
                    "output_path": chunk_path,
                },
                created_by=self.controller_id,
                parent_plan_id=parent_id,
                plan_id=(
                    f"plan-foundation-corpus-{session_id}-"
                    f"chunk-{chunk['chunk_index']:04d}"
                ),
                authorization={
                    "allow_weight_updates": False,
                    "allow_checkpoint_promotion": False,
                    "allow_auto_advance": False,
                },
            )
            parent_id = chunk_plan["plan_id"]
        child = self.ledger.create_plan(
            kind="cortex_block",
            mode="live",
            payload={
                "jsonl_paths": chunk_paths,
                "curriculum_id": session_id,
                "curriculum_sha256": chunks[0]["curriculum_sha256"],
                "concept": "broad_foundational_replay",
                "output_checkpoint": f"core/cortex/{session_id}.pt",
                "runner_args": [
                    "--parent",
                    parent_checkpoint,
                    "--epochs",
                    "1",
                    "--batch-size",
                    "1",
                    "--lr",
                    "0.00001",
                    "--ingress-device",
                    "cuda:0",
                    "--core-device",
                    "cuda:1",
                    "--train-scope",
                    "full",
                    "--local-files-only",
                    "--probe-max-new-tokens",
                    "24",
                ],
            },
            created_by=self.controller_id,
            parent_plan_id=parent_id,
            plan_id=f"plan-foundation-train-{session_id}",
            authorization={
                "allow_weight_updates": True,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
        )
        state["current_plan_id"] = child["plan_id"]
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [
                {
                    "at": state["updated_at"],
                    "status": "running",
                    "detail": (
                        f"Created {len(chunks)} resumable corpus chunks and the "
                        f"operator-directed {FOUNDATION_BLOCK_SIZE}-example foundational "
                        f"replay block {child['plan_id']} after {parent_plan_id}."
                    ),
                }
            ]
        )[-100:]
        self.store.write(state)
        return {
            "active": True,
            "action": "created_foundational_replay_block",
            "plan_id": child["plan_id"],
            "examples": FOUNDATION_BLOCK_SIZE,
            "corpus_chunks": len(chunks),
        }

    @staticmethod
    def _uses_prepared_allowlist_wave(state: dict[str, Any]) -> bool:
        """Keep prepared vocabulary waves at strategic decision boundaries.

        Generic foundational bootstrap campaigns may deterministically auto-continue
        with the repository-wide replay sampler.  A campaign carrying an immutable
        allowlist-wave manifest has a different, operator-selected curriculum, so its
        evaluator must return to the orchestrator instead of silently substituting the
        generic sampler after the first block.
        """
        return any(
            isinstance(relative, str)
            and relative.startswith("training/pipeline/cortex/allowlist_waves/")
            and relative.endswith("/manifest.json")
            for relative in state.get("context_files", [])
        )

    def _rollover(
        self,
        state: dict[str, Any],
        *,
        seed_plan_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Close one bounded research wave and immediately start its successor."""
        terminal_report = self.ledger.report(seed_plan_id)
        terminal_decision = (
            terminal_report.get("result", {}).get("decision")
            if isinstance(terminal_report, dict)
            else None
        )
        predecessor_advisory = (
            terminal_decision.get("rationale")
            if isinstance(terminal_decision, dict)
            else None
        )
        seed_plan_id = self._resolve_rollover_seed(seed_plan_id)
        completed = copy.deepcopy(state)
        completed["status"] = "completed"
        completed["stop_reason"] = reason
        completed["updated_at"] = utc_now()
        completed["history"] = (
            completed["history"]
            + [
                {
                    "at": completed["updated_at"],
                    "status": "completed",
                    "detail": f"{reason} Autonomous rollover authorized.",
                }
            ]
        )[-100:]

        development = self.development_store.reconcile()
        previous_evolution = self.evolution_store.read()
        requested_generation = (
            int(previous_evolution.get("generation", 0)) + 1
            if previous_evolution
            else 1
        )
        stage_slug = str(development["stage"]).replace("_", "-")
        campaign_id, generation = self._next_evolution_identity(
            stage_slug,
            minimum_generation=requested_generation,
        )
        objective = self.evolution_store.objective(
            development,
            predecessor_advisory=predecessor_advisory,
        )
        now = utc_now()
        contexts = self._review_context_files(state)
        for relative in (
            "training/pipeline/cortex/evolution_goal.json",
            "training/pipeline/cortex/development_policy.json",
            "training/pipeline/cortex/autonomous_campaign.md",
            "training/pipeline/script_schema.json",
        ):
            if (
                relative not in contexts
                and (self.repo_root / relative).is_file()
                and len(contexts) < 32
            ):
                contexts.append(relative)
        budgets = self.evolution_store.budgets()
        try:
            CampaignRegistry(self.repo_root).get_or_allocate(
                campaign_id=campaign_id,
                objective=objective,
                created_at=now,
            )
        except CampaignArtifactError as exc:
            raise CampaignError(f"cannot allocate rollover campaign: {exc}") from exc
        successor = {
            "schema_version": CAMPAIGN_SCHEMA,
            "campaign_id": campaign_id,
            "status": "running",
            "mode": "live",
            "objective": objective,
            "created_at": now,
            "updated_at": now,
            "deadline_at": self.evolution_store.deadline(),
            "seed_plan_id": seed_plan_id,
            "root_boundary_plan_id": None,
            "current_plan_id": seed_plan_id,
            "boundary_index": 0,
            "authorization": dict(state["authorization"]),
            "allowed_child_kinds": ["executor_job"],
            "allowed_phase_ids": [],
            "context_files": contexts,
            "budgets": budgets,
            "usage": {key: 0 for key in COUNTED_KINDS.values()},
            "stop_reason": None,
            "regime": "standard",
            "play": None,
            "governance": {
                "pending_directive": None,
                "last_review_id": None,
                "last_reviewed_mutations": 0,
            },
            "history": [
                {
                    "at": now,
                    "status": "running",
                    "detail": (
                        f"Evolution generation {generation} rolled over from "
                        f"{state['campaign_id']} at terminal seed {seed_plan_id}."
                    ),
                }
            ],
        }
        CampaignStateStore.validate(successor)
        self.store.write(successor)
        self.evolution_store.record(
            campaign=successor,
            development=development,
            generation=generation,
            completed_campaign_id=str(completed["campaign_id"]),
            predecessor_advisory=predecessor_advisory,
        )
        return {
            "active": True,
            "action": "rolled_over",
            "reason": reason,
            "completed_campaign_state": completed,
            "campaign_id": successor["campaign_id"],
            "seed_plan_id": seed_plan_id,
            "generation": generation,
        }

    def _next_evolution_identity(
        self,
        stage_slug: str,
        *,
        minimum_generation: int,
    ) -> tuple[str, int]:
        used: set[str] = set()
        try:
            used.update(
                str(row.get("campaign_id"))
                for row in CampaignRegistry(self.repo_root).read()["campaigns"]
                if isinstance(row, dict) and isinstance(row.get("campaign_id"), str)
            )
        except CampaignArtifactError:
            pass
        for plan in self._plans().values():
            payload = plan.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            campaign = payload.get("campaign")
            if isinstance(campaign, dict) and isinstance(
                campaign.get("campaign_id"), str
            ):
                used.add(campaign["campaign_id"])
            boundary = payload.get("boundary_id")
            if isinstance(boundary, str):
                match = re.match(r"^(cortex-evolution-.+-g[0-9]{4})-b[0-9]{4}$", boundary)
                if match:
                    used.add(match.group(1))
        generation = max(1, minimum_generation)
        while True:
            campaign_id = f"cortex-evolution-{stage_slug}-g{generation:04d}"
            if campaign_id not in used:
                return campaign_id, generation
            generation += 1

    @staticmethod
    def _existing_boundary_belongs_to_campaign(
        plan: dict[str, Any],
        *,
        state: dict[str, Any],
        parent_plan_id: str,
        boundary_index: int,
    ) -> bool:
        payload = plan.get("payload")
        campaign = payload.get("campaign") if isinstance(payload, dict) else None
        return bool(
            plan.get("kind") == "strategic_decision"
            and plan.get("parent_plan_id") == parent_plan_id
            and isinstance(campaign, dict)
            and campaign.get("campaign_id") == state["campaign_id"]
            and campaign.get("boundary_index") == boundary_index
        )

    @staticmethod
    def _identity_repair_is_safe(state: dict[str, Any]) -> bool:
        return bool(
            state["boundary_index"] == 0
            and state["root_boundary_plan_id"] is None
            and all(int(value) == 0 for value in state["usage"].values())
            and EVOLUTION_CAMPAIGN_ID.fullmatch(state["campaign_id"])
        )

    def _repair_evolution_identity(
        self,
        state: dict[str, Any],
        *,
        collision_plan_id: str,
        development_state: dict[str, Any],
    ) -> dict[str, Any]:
        match = EVOLUTION_CAMPAIGN_ID.fullmatch(state["campaign_id"])
        if match is None:
            raise CampaignError("campaign identity is not automatically repairable")
        old_campaign_id = state["campaign_id"]
        campaign_id, generation = self._next_evolution_identity(
            match.group("stage"),
            minimum_generation=int(match.group("generation")),
        )
        CampaignRegistry(self.repo_root).get_or_allocate(
            campaign_id=campaign_id,
            objective=state["objective"],
            created_at=state["created_at"],
        )
        state["campaign_id"] = campaign_id
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [
                {
                    "at": state["updated_at"],
                    "status": "running",
                    "detail": (
                        f"Re-keyed campaign from {old_campaign_id} to {campaign_id}; "
                        f"{collision_plan_id} belonged to an older immutable lineage."
                    ),
                }
            ]
        )[-100:]
        self.store.write(state)
        self.evolution_store.record(
            campaign=state,
            development=development_state,
            generation=generation,
        )
        try:
            self.ledger.timing.record(
                "campaign.identity_repaired",
                "campaign-controller",
                old_campaign_id=old_campaign_id,
                campaign_id=campaign_id,
                collision_plan_id=collision_plan_id,
                generation=generation,
            )
        except (OSError, ValueError, TypeError):
            pass
        self.message_store.write_system_notice(
            f"campaign-identity-repaired:{old_campaign_id}:{campaign_id}",
            "Campaign identity repaired automatically",
            (
                f"The active campaign was safely re-keyed from {old_campaign_id} "
                f"to {campaign_id} after detecting a historical plan collision."
            ),
            metadata={
                "old_campaign_id": old_campaign_id,
                "campaign_id": campaign_id,
                "collision_plan_id": collision_plan_id,
            },
        )
        return state

    def _resolve_rollover_seed(self, plan_id: str) -> str:
        """Find the nearest terminal ancestor carrying an authoritative checkpoint."""
        seen: set[str] = set()
        cursor: str | None = plan_id
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            plan = self.ledger.plan(cursor)
            receipt = self.ledger.receipt(cursor)
            report = self.ledger.report(cursor)
            result = report.get("result") if isinstance(report, dict) else None
            checkpoint = (
                result.get("checkpoint_after") if isinstance(result, dict) else None
            )
            if (
                receipt is not None
                and receipt["status"] in TERMINAL_RECEIPT_STATUSES
                and isinstance(checkpoint, str)
                and checkpoint
            ):
                return cursor
            cursor = (
                plan.get("parent_plan_id") if isinstance(plan, dict) else None
            )
        raise CampaignError(
            f"cannot find a terminal checkpoint-bearing rollover seed from {plan_id}"
        )

    def set_status(self, status: str, reason: str) -> dict[str, Any]:
        if status not in {"running", "paused"}:
            raise CampaignError("manual status must be running or paused")
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                raise CampaignError("no campaign exists")
            if status == "running" and state["status"] not in {"waiting", "paused"}:
                raise CampaignError(f"cannot resume campaign from {state['status']}")
            if status == "paused" and state["status"] != "running":
                raise CampaignError(f"cannot pause campaign from {state['status']}")
            if status == "running":
                resumed = self._resume_after_strategic_wait(state, reason=reason)
                if resumed is not None:
                    return resumed
            state["status"] = status
            state["stop_reason"] = None if status == "running" else reason
            state["updated_at"] = utc_now()
            state["history"] = (
                state["history"]
                + [{"at": state["updated_at"], "status": status, "detail": reason}]
            )[-100:]
            self.store.write(state)
            return state

    def extend_budgets(
        self,
        requested: dict[str, int],
        *,
        reason: str,
    ) -> dict[str, Any]:
        """Apply an explicit, auditable increase without resuming the campaign."""

        if not requested or not reason.strip():
            raise CampaignError("budget extension and reason must be non-empty")
        valid = set(COUNTED_KINDS.values())
        if not set(requested).issubset(valid):
            raise CampaignError("budget extension contains an unknown budget")
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                raise CampaignError("no campaign exists")
            previous = dict(state["budgets"])
            updated = dict(previous)
            for key, value in requested.items():
                if isinstance(value, bool) or not isinstance(value, int):
                    raise CampaignError(f"{key} extension must be an integer")
                if value < previous[key]:
                    raise CampaignError(f"{key} extension cannot reduce the budget")
                if value > MAX_CAMPAIGN_BUDGET:
                    raise CampaignError(
                        f"{key} extension may not exceed {MAX_CAMPAIGN_BUDGET}"
                    )
                updated[key] = value
            state["budgets"] = updated
            state["usage"] = self._usage(state, self._plans())
            state["updated_at"] = utc_now()
            state["history"] = (
                state["history"]
                + [
                    {
                        "at": state["updated_at"],
                        "status": state["status"],
                        "detail": (
                            "Budget extension applied without resuming: "
                            f"{json.dumps(previous, sort_keys=True)} -> "
                            f"{json.dumps(updated, sort_keys=True)}. Reason: {reason.strip()}"
                        ),
                    }
                ]
            )[-100:]
            self.store.write(state)
            return state

    def record_governance_review(
        self,
        *,
        review_id: str,
        mutation_count: int,
    ) -> dict[str, Any]:
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                raise CampaignError("no campaign exists")
            state["governance"]["last_review_id"] = review_id
            state["governance"]["last_reviewed_mutations"] = mutation_count
            state["updated_at"] = utc_now()
            self.store.write(state)
            return state

    def apply_governance_decision(
        self,
        action: str,
        rationale: str,
    ) -> dict[str, Any]:
        allowed = {
            "continue_as_proposed",
            "continue_with_conditions",
            "require_replan",
            "start_new_branch",
            "pause_for_human",
            "terminate_branch",
        }
        if action not in allowed or not rationale.strip():
            raise CampaignError("invalid governance decision")
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                raise CampaignError("no campaign exists")
            if action == "pause_for_human":
                self._stop(
                    state,
                    "waiting",
                    f"SOL governance decision: {rationale.strip()}",
                    event="sol-governance-human",
                )
                return state
            if action in {"start_new_branch", "terminate_branch"}:
                started = self._start_next_play_branch(
                    state,
                    status=f"sol_{action}",
                    reason=f"SOL governance decision: {rationale.strip()}",
                )
                if started:
                    if action == "terminate_branch":
                        state["governance"]["pending_directive"] = None
                    else:
                        state["governance"]["pending_directive"] = (
                            f"SOL binding decision ({action}): {rationale.strip()}"
                        )
                    state["updated_at"] = utc_now()
                    state["history"] = (
                        state["history"]
                        + [{
                            "at": state["updated_at"],
                            "status": state["status"],
                            "detail": f"SOL governance decision {action}: {rationale.strip()}",
                        }]
                    )[-100:]
                    self.store.write(state)
                    return state
            if action != "continue_as_proposed":
                state["governance"]["pending_directive"] = (
                    f"SOL binding decision ({action}): {rationale.strip()}"
                )
            state["updated_at"] = utc_now()
            state["history"] = (
                state["history"]
                + [{
                    "at": state["updated_at"],
                    "status": state["status"],
                    "detail": f"SOL governance decision {action}: {rationale.strip()}",
                }]
            )[-100:]
            self.store.write(state)
            return state

    def _resume_after_strategic_wait(
        self,
        state: dict[str, Any],
        *,
        reason: str,
    ) -> dict[str, Any] | None:
        """Move an operator-approved strategic wait onto a fresh boundary.

        A completed strategic decision is immutable. Merely changing the campaign
        status to running would make reconcile consume the same wait/request_human
        decision again and immediately return the campaign to waiting.
        """

        current = state["current_plan_id"]
        plan = self.ledger.plan(current)
        receipt = self.ledger.receipt(current)
        report = self.ledger.report(current)
        result = report.get("result") if isinstance(report, dict) else None
        decision = result.get("decision") if isinstance(result, dict) else None
        action = decision.get("action") if isinstance(decision, dict) else None
        if (
            not isinstance(plan, dict)
            or plan.get("kind") != "strategic_decision"
            or not isinstance(receipt, dict)
            or receipt.get("status") not in TERMINAL_RECEIPT_STATUSES
            or action not in {"wait", "request_human"}
        ):
            return None

        plans = self._plans()
        usage = self._usage(state, plans)
        remaining = {
            key: state["budgets"][key] - usage[key]
            for key in state["budgets"]
        }
        if remaining["strategic_boundaries"] < 1:
            raise CampaignError(
                "cannot resume campaign: no strategic boundary budget remains"
            )
        if time.time() >= _parse_time(state["deadline_at"]):
            raise CampaignError("cannot resume campaign: campaign deadline has passed")

        allowed = [
            kind
            for kind in state["allowed_child_kinds"]
            if remaining.get(COUNTED_KINDS[kind], 0) > 0
        ]
        state["status"] = "running"
        state["stop_reason"] = None
        if self._maybe_start_next_play_branch_for_block_capacity(state):
            if state["status"] != "running":
                return state
        boundary_index = state["boundary_index"] + 1
        boundary_id = f"{state['campaign_id']}-b{boundary_index:04d}"
        plan_id = f"plan-campaign-{boundary_id}"
        if self.ledger.plan(plan_id) is not None:
            raise CampaignError(f"resume boundary already exists: {plan_id}")
        campaign = {
            "campaign_id": state["campaign_id"],
            "boundary_index": boundary_index,
            "constraints": {
                "remaining_phase_blocks": max(0, remaining["phase_blocks"]),
                "remaining_executor_jobs": max(0, remaining["executor_jobs"]),
                "remaining_trainer_sessions": max(0, remaining["trainer_sessions"]),
                "allowed_phase_ids": state["allowed_phase_ids"],
                "max_phase_continuation_blocks": 0,
                "max_auto_sessions": 0,
            },
        }
        if state.get("regime") == "play":
            campaign["play"] = self._play_campaign_snapshot(state)
        instructions = self._instructions(
            state,
            current,
            remaining,
            development_state=self.development_store.reconcile(),
            review_only=not allowed,
        ) + (
            "\n\nAn operator explicitly resumed the campaign after the preceding "
            f"strategic {action}. The operator's recovery note is: {reason} "
            "Treat the preceding decision as resolved external state, not as a "
            "result to repeat. No weights changed while the campaign was waiting. "
            "Choose one fresh bounded next action with new boundary-derived "
            "identifiers."
        )
        strategic = self.ledger.create_plan(
            kind="strategic_decision",
            mode=state["mode"],
            payload={
                "boundary_id": boundary_id,
                "title": (
                    f"{state['campaign_id']} boundary {boundary_index}: "
                    "resume after operator recovery"
                ),
                "instructions": instructions,
                "context_files": (
                    self._review_context_files(state)
                    if not allowed
                    else state["context_files"]
                ),
                "allowed_child_kinds": allowed,
                "campaign": campaign,
            },
            created_by=self.controller_id,
            parent_plan_id=current,
            plan_id=plan_id,
            authorization=state["authorization"],
        )
        state["status"] = "running"
        state["stop_reason"] = None
        state["boundary_index"] = boundary_index
        state["current_plan_id"] = strategic["plan_id"]
        state["usage"] = self._usage(state, self._plans())
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [
                {
                    "at": state["updated_at"],
                    "status": "running",
                    "detail": (
                        f"Operator recovery created fresh strategic boundary "
                        f"{strategic['plan_id']} after {current}: {reason}"
                    ),
                }
            ]
        )[-100:]
        self.store.write(state)
        return state

    def recover_repairable_blocker(self) -> dict[str, Any]:
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                raise CampaignError("no campaign exists")
            if state["status"] != "blocked":
                raise CampaignError("campaign is not blocked")
            receipt = self.ledger.receipt(state["current_plan_id"])
            if not self._repairable_strategic_context_failure(receipt):
                raise CampaignError(
                    "blocked campaign does not have a repairable strategic context failure"
                )
            state["status"] = "running"
            state["stop_reason"] = None
            state["updated_at"] = utc_now()
            state["history"] = (
                state["history"]
                + [
                    {
                        "at": state["updated_at"],
                        "status": "running",
                        "detail": (
                            "Recovered a strategic boundary blocked by a nonexistent "
                            "optional executor context file."
                        ),
                    }
                ]
            )[-100:]
            self.store.write(state)
            return state

    def recover_from_emergency(self, reason: str) -> dict[str, Any]:
        """Create one fresh immutable boundary after SOL approves emergency recovery."""

        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                raise CampaignError("no campaign exists")
            if state["status"] != "blocked":
                raise CampaignError("emergency recovery requires a blocked campaign")
            current = state["current_plan_id"]
            plan = self.ledger.plan(current)
            receipt = self.ledger.receipt(current)
            if (
                plan is None
                or plan.get("kind") != "strategic_decision"
                or receipt is None
                or receipt.get("status") not in {"blocked", "dead_letter"}
            ):
                raise CampaignError(
                    "blocked campaign does not have a terminal strategic boundary"
                )
            result = self._create_strategic_provider_retry(
                state,
                failed_plan_id=current,
                ignore_cooldown=True,
                recovery_reason=reason,
            )
            (self.ledger.plans_dir / ".wake").touch()
            return result

    def close(self, reason: str) -> dict[str, Any]:
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                raise CampaignError("no campaign exists")
            if state["status"] == "running":
                raise CampaignError("pause the running campaign before closing it")
            state["status"] = "completed"
            state["stop_reason"] = reason
            state["updated_at"] = utc_now()
            state["history"] = (
                state["history"]
                + [
                    {
                        "at": state["updated_at"],
                        "status": "completed",
                        "detail": reason,
                    }
                ]
            )[-100:]
            self.store.write(state)
            return state

    def _stop(
        self,
        state: dict[str, Any],
        status: str,
        reason: str,
        *,
        event: str,
    ) -> None:
        state["status"] = status
        state["stop_reason"] = reason
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [{"at": state["updated_at"], "status": status, "detail": reason}]
        )[-100:]
        self.store.write(state)
        self.message_store.write_system_notice(
            f"campaign-stop:{state['campaign_id']}:{event}:{state['boundary_index']}",
            f"Autonomous campaign {status}: {state['campaign_id']}",
            reason,
            metadata={
                "campaign_id": state["campaign_id"],
                "status": status,
                "current_plan_id": state["current_plan_id"],
            },
        )

    def _await_sol_budget_review(
        self,
        state: dict[str, Any],
        *,
        usage: dict[str, int],
    ) -> dict[str, Any]:
        exhausted = [
            key
            for key, ceiling in state["budgets"].items()
            if usage.get(key, 0) >= ceiling
        ]
        state["status"] = "waiting"
        state["stop_reason"] = (
            "Research budget reached; awaiting automatic SOL adjudication. "
            f"Reached: {', '.join(exhausted) or 'an allowed child budget'}."
        )
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [{
                "at": state["updated_at"],
                "status": "waiting",
                "detail": state["stop_reason"],
            }]
        )[-100:]
        self.store.write(state)
        return {
            "active": False,
            "action": "budget_review_required",
            "exhausted": exhausted,
            "usage": usage,
            "budgets": state["budgets"],
        }

    def _strategic_boundary_wait_seconds(
        self,
        state: dict[str, Any],
        *,
        now: float | None = None,
    ) -> int:
        """Return seconds until the campaign may create its next strategic boundary.

        Strategic boundaries are paced from the terminal trainbox report that made
        orchestration necessary. This gives the training box a fixed cooldown after it
        finishes instead of tying the next wake to the previous orchestrator run.
        """

        if self.strategic_boundary_interval_seconds == 0:
            return 0
        report = self.ledger.report(state["current_plan_id"])
        if report is None:
            return 0
        completed_at = _parse_time(report["completed_at"])
        timestamp = time.time() if now is None else now
        next_allowed = completed_at + self.strategic_boundary_interval_seconds
        return max(0, int(next_allowed - timestamp + 0.999))

    @staticmethod
    def _repairable_strategic_context_failure(
        receipt: dict[str, Any] | None,
    ) -> bool:
        return bool(
            isinstance(receipt, dict)
            and receipt.get("status") in {"blocked", "dead_letter"}
            and "executor context file does not exist in the repository:"
            in str(receipt.get("last_error") or "")
        )

    def _blocked_provider_capacity_recovered(self, state: dict[str, Any]) -> bool:
        receipt = self.ledger.receipt(state["current_plan_id"])
        report = self.ledger.report(state["current_plan_id"])
        return (
            self._strategic_provider_capacity_block(receipt, report)
            and self._provider_capacity_available()
        )

    @staticmethod
    def _strategic_provider_capacity_block(
        receipt: dict[str, Any] | None,
        report: dict[str, Any] | None,
    ) -> bool:
        if (
            not isinstance(receipt, dict)
            or receipt.get("status") not in {"blocked", "dead_letter"}
        ):
            return False
        result = report.get("result") if isinstance(report, dict) else None
        if isinstance(result, dict) and result.get("error_type") == "both_providers_limited":
            return True
        error = str(receipt.get("last_error") or "")
        return any(
            marker in error
            for marker in (
                "Codex and Fugu are rate-limited",
                "returned empty content",
                "returned an unexpected response shape",
                "returned invalid JSON",
                "invocation failed:",
            )
        )

    def _provider_capacity_available(self) -> bool:
        path = self.ledger.root / "provider/status.json"
        try:
            status = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return False
        if not isinstance(status, dict):
            return False
        codex = status.get("codex")
        if isinstance(codex, dict) and codex.get("state") == "available":
            return True
        fugu = status.get("fugu")
        if not isinstance(fugu, dict):
            return False
        return fugu.get("state") == "configured" and fugu.get("limited") is not True

    def _create_strategic_provider_retry(
        self,
        state: dict[str, Any],
        *,
        failed_plan_id: str,
        ignore_cooldown: bool = False,
        recovery_reason: str | None = None,
    ) -> dict[str, Any]:
        usage = self._usage(state, self._plans())
        remaining = {
            key: state["budgets"][key] - usage[key]
            for key in state["budgets"]
        }
        if remaining["strategic_boundaries"] < 1:
            self._stop(
                state,
                "blocked",
                (
                    "A strategic provider-capacity block cleared, but the campaign "
                    "has no remaining strategic boundary budget for a retry."
                ),
                event="strategic-provider-retry-budget",
            )
            return {"active": False, "action": "blocked_provider_retry_budget"}
        wait_seconds = (
            0 if ignore_cooldown else self._strategic_boundary_wait_seconds(state)
        )
        if wait_seconds > 0:
            state["status"] = "running"
            state["stop_reason"] = None
            state["updated_at"] = utc_now()
            self.store.write(state)
            receipt = self.ledger.receipt(failed_plan_id)
            return {
                "active": True,
                "action": "waiting_for_orchestrator_window",
                "plan_id": failed_plan_id,
                "plan_status": receipt["status"] if receipt is not None else "missing",
                "next_attempt_in_seconds": wait_seconds,
                "cadence_seconds": self.strategic_boundary_interval_seconds,
            }

        boundary_index = state["boundary_index"] + 1
        boundary_id = f"{state['campaign_id']}-b{boundary_index:04d}"
        plan_id = f"plan-campaign-{boundary_id}"
        allowed = [
            kind
            for kind in state["allowed_child_kinds"]
            if remaining.get(COUNTED_KINDS[kind], 0) > 0
        ]
        campaign = {
            "campaign_id": state["campaign_id"],
            "boundary_index": boundary_index,
            "constraints": {
                "remaining_phase_blocks": max(0, remaining["phase_blocks"]),
                "remaining_executor_jobs": max(0, remaining["executor_jobs"]),
                "remaining_trainer_sessions": max(0, remaining["trainer_sessions"]),
                "allowed_phase_ids": state["allowed_phase_ids"],
                "max_phase_continuation_blocks": 0,
                "max_auto_sessions": 0,
            },
        }
        instructions = self._instructions(
            state,
            failed_plan_id,
            remaining,
            development_state=self.development_store.reconcile(),
            review_only=not allowed,
        ) + (
            "\n\nThe preceding strategic boundary could not run because its provider was "
            "temporarily unavailable or returned an invalid response. Provider capacity "
            "is now available. No executor ran and no weights changed. Propose one fresh bounded "
            "next action with new boundary-derived identifiers; do not reuse artifacts "
            "from the blocked boundary."
        )
        if recovery_reason:
            instructions += (
                "\n\nSOL emergency recovery rationale: " + recovery_reason.strip()
            )
        strategic = self.ledger.create_plan(
            kind="strategic_decision",
            mode=state["mode"],
            payload={
                "boundary_id": boundary_id,
                "title": (
                    f"{state['campaign_id']} boundary {boundary_index}: "
                    "retry after provider capacity recovered"
                ),
                "instructions": instructions,
                "context_files": (
                    self._review_context_files(state)
                    if not allowed
                    else state["context_files"]
                ),
                "allowed_child_kinds": allowed,
                "campaign": campaign,
            },
            created_by=self.controller_id,
            parent_plan_id=failed_plan_id,
            plan_id=plan_id,
            authorization=state["authorization"],
        )
        state["status"] = "running"
        state["stop_reason"] = None
        state["boundary_index"] = boundary_index
        state["current_plan_id"] = strategic["plan_id"]
        state["usage"] = self._usage(state, self._plans())
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [
                {
                    "at": state["updated_at"],
                    "status": "running",
                    "detail": (
                        f"Created strategic provider-capacity retry {strategic['plan_id']} "
                        f"after {failed_plan_id}; no weights had changed."
                    ),
                }
            ]
        )[-100:]
        self.store.write(state)
        return {
            "active": True,
            "action": "created_strategic_provider_retry",
            "plan_id": strategic["plan_id"],
        }

    def _create_strategic_context_repair(
        self,
        state: dict[str, Any],
        *,
        failed_plan_id: str,
        error: str,
    ) -> dict[str, Any]:
        usage = self._usage(state, self._plans())
        remaining = {
            key: state["budgets"][key] - usage[key]
            for key in state["budgets"]
        }
        if (
            state["allowed_child_kinds"] != ["executor_job"]
            or state["allowed_phase_ids"]
            or remaining["strategic_boundaries"] < 1
            or remaining["executor_jobs"] < 1
        ):
            self._stop(
                state,
                "blocked",
                (
                    "A strategic context-path failure was repairable, but the "
                    "campaign has no compatible repair budget."
                ),
                event="strategic-context-repair-budget",
            )
            return {"active": False, "action": "blocked_repair_budget"}
        wait_seconds = self._strategic_boundary_wait_seconds(state)
        if wait_seconds > 0:
            receipt = self.ledger.receipt(failed_plan_id)
            state["updated_at"] = utc_now()
            self.store.write(state)
            return {
                "active": True,
                "action": "waiting_for_orchestrator_window",
                "plan_id": failed_plan_id,
                "plan_status": receipt["status"] if receipt is not None else "missing",
                "next_attempt_in_seconds": wait_seconds,
                "cadence_seconds": self.strategic_boundary_interval_seconds,
            }

        boundary_index = state["boundary_index"] + 1
        boundary_id = f"{state['campaign_id']}-b{boundary_index:04d}"
        plan_id = f"plan-campaign-{boundary_id}"
        campaign = {
            "campaign_id": state["campaign_id"],
            "boundary_index": boundary_index,
            "constraints": {
                "remaining_phase_blocks": max(0, remaining["phase_blocks"]),
                "remaining_executor_jobs": max(0, remaining["executor_jobs"]),
                "remaining_trainer_sessions": max(0, remaining["trainer_sessions"]),
                "allowed_phase_ids": state["allowed_phase_ids"],
                "max_phase_continuation_blocks": 0,
                "max_auto_sessions": 0,
            },
        }
        instructions = self._instructions(
            state,
            failed_plan_id,
            remaining,
            development_state=self.development_store.reconcile(),
        ) + (
            "\n\nThe preceding strategic proposal exhausted its retries before a child "
            "was created because it referenced a nonexistent optional executor context "
            f"file. The deterministic error was: {error}. No executor ran and no weights "
            "changed. Propose one corrected bounded Cortex executor_job. Include only "
            "context files that actually exist under tracked training/, training_data/, "
            "or training_material/ roots; summarize any other evidence directly in task "
            "instructions. Continue from development_state.current_checkpoint and use "
            "fresh identifiers."
        )
        strategic = self.ledger.create_plan(
            kind="strategic_decision",
            mode=state["mode"],
            payload={
                "boundary_id": boundary_id,
                "title": (
                    f"{state['campaign_id']} boundary {boundary_index}: "
                    "repair invalid context proposal"
                ),
                "instructions": instructions,
                "context_files": state["context_files"],
                "allowed_child_kinds": ["executor_job"],
                "campaign": campaign,
            },
            created_by=self.controller_id,
            parent_plan_id=failed_plan_id,
            plan_id=plan_id,
            authorization=state["authorization"],
        )
        state["status"] = "running"
        state["stop_reason"] = None
        state["boundary_index"] = boundary_index
        state["current_plan_id"] = strategic["plan_id"]
        state["usage"] = self._usage(state, self._plans())
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [
                {
                    "at": state["updated_at"],
                    "status": "running",
                    "detail": (
                        f"Created strategic context repair {strategic['plan_id']} "
                        f"after {failed_plan_id}; no weights had changed."
                    ),
                }
            ]
        )[-100:]
        self.store.write(state)
        return {
            "active": True,
            "action": "created_strategic_context_repair",
            "plan_id": strategic["plan_id"],
        }

    def _create_prepared_wave_technical_retry(
        self,
        state: dict[str, Any],
        *,
        failed_plan: dict[str, Any],
        receipt: dict[str, Any],
        plans: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Retry immutable prepared data without spending another strategy turn."""

        error = str(receipt.get("last_error") or "")
        if not any(
            marker in error
            for marker in (
                "CortexScriptError",
                "training answer exceeds",
                "has no teacher or acceptable training answer",
            )
        ):
            return None
        parent_id = failed_plan.get("parent_plan_id")
        executor = plans.get(parent_id) if isinstance(parent_id, str) else None
        task = executor.get("payload", {}).get("task") if isinstance(executor, dict) else None
        task_context = task.get("context_files") if isinstance(task, dict) else None
        candidates = [
            relative
            for relative in (task_context if isinstance(task_context, list) else [])
            if isinstance(relative, str)
            and relative.startswith("training/pipeline/cortex/allowlist_waves/")
            and re.search(r"/block-[0-9]{2}\.jsonl$", relative)
            and relative in state.get("context_files", [])
        ]
        if len(candidates) != 1:
            return None
        source_relative = candidates[0]
        source = (self.repo_root / source_relative).resolve()
        if self.repo_root not in source.parents or not source.is_file():
            return None
        lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) != FOUNDATION_BLOCK_SIZE:
            return None
        try:
            rows = [json.loads(line) for line in lines]
        except json.JSONDecodeError:
            return None
        if not all(
            isinstance(row, dict)
            and isinstance(row.get("prompt"), str)
            and row["prompt"]
            and isinstance(row.get("completion"), str)
            and row["completion"]
            for row in rows
        ):
            return None

        manifest_relative = source_relative.rsplit("/", 1)[0] + "/manifest.json"
        if manifest_relative not in state.get("context_files", []):
            return None
        try:
            manifest = json.loads(
                (self.repo_root / manifest_relative).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return None
        expected_hash = next(
            (
                block.get("training_sha256")
                for block in manifest.get("blocks", [])
                if isinstance(block, dict)
                and block.get("training_path") == source_relative
            ),
            None,
        )
        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            return None

        retry_id = f"{failed_plan['plan_id']}-technical-retry-01"
        retry = self.ledger.plan(retry_id)
        if retry is None:
            payload = failed_plan.get("payload", {})
            runner_args = payload.get("runner_args")
            output_checkpoint = payload.get("output_checkpoint")
            if (
                not isinstance(runner_args, list)
                or not all(isinstance(value, str) for value in runner_args)
                or not isinstance(output_checkpoint, str)
                or not output_checkpoint
            ):
                return None
            retry = self.ledger.create_plan(
                kind="cortex_block",
                mode=failed_plan["mode"],
                payload={
                    "jsonl_path": source_relative,
                    "output_checkpoint": output_checkpoint,
                    "runner_args": runner_args,
                },
                created_by=self.controller_id,
                parent_plan_id=failed_plan["plan_id"],
                plan_id=retry_id,
                authorization=failed_plan["authorization"],
                max_attempts=3,
            )
        state["status"] = "running"
        state["stop_reason"] = None
        state["current_plan_id"] = retry["plan_id"]
        state["usage"] = self._usage(state, self._plans())
        state["updated_at"] = utc_now()
        state["history"] = (
            state["history"]
            + [
                {
                    "at": state["updated_at"],
                    "status": "running",
                    "detail": (
                        f"Created non-chargeable technical retry {retry['plan_id']} from "
                        f"the verified immutable prepared block after {failed_plan['plan_id']}."
                    ),
                }
            ]
        )[-100:]
        self.store.write(state)
        self.ledger.wake_path.touch()
        return {
            "active": True,
            "action": "created_prepared_wave_technical_retry",
            "plan_id": retry["plan_id"],
            "source": source_relative,
            "research_budget_charged": False,
        }

    def _plans(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for path in sorted(self.ledger.plans_dir.glob("*.json")):
            plan = self.ledger.plan(path.stem)
            if plan is not None:
                result[plan["plan_id"]] = plan
        return result

    @staticmethod
    def _children(
        plans: dict[str, dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for plan in plans.values():
            parent = plan["parent_plan_id"]
            if parent is not None:
                result.setdefault(parent, []).append(plan)
        for descendants in result.values():
            descendants.sort(key=lambda plan: (plan["created_at"], plan["plan_id"]))
            # Evaluation was introduced after the first Cortex commissioning
            # runs. A retroactive evaluation can therefore be a sidecar sibling
            # of an already-existing strategic continuation. Preserve the
            # original single lineage in that migration case; new campaigns
            # always have evaluation as the sole child before continuation.
            non_evaluations = [
                plan for plan in descendants if plan["kind"] != "cortex_evaluation"
            ]
            if non_evaluations and len(non_evaluations) < len(descendants):
                descendants[:] = non_evaluations
        return result

    def _usage(
        self,
        state: dict[str, Any],
        plans: dict[str, dict[str, Any]],
    ) -> dict[str, int]:
        usage = {key: 0 for key in COUNTED_KINDS.values()}
        root = state["root_boundary_plan_id"]
        if root is None:
            return usage
        children = self._children(plans)
        queue = [root]
        seen: set[str] = set()
        while queue:
            plan_id = queue.pop()
            if plan_id in seen or plan_id not in plans:
                continue
            seen.add(plan_id)
            plan = plans[plan_id]
            kind = plan["kind"]
            key = COUNTED_KINDS.get(kind)
            if key is not None and self._plan_consumes_research_budget(
                plan,
                plans=plans,
                children=children,
            ):
                usage[key] += 1
            queue.extend(child["plan_id"] for child in children.get(plan_id, []))
        return usage

    def _plan_consumes_research_budget(
        self,
        plan: dict[str, Any],
        *,
        plans: dict[str, dict[str, Any]],
        children: dict[str, list[dict[str, Any]]],
    ) -> bool:
        """Charge research outcomes, never failed operational attempts.

        A strategic plan is charged only when its local segment reaches a durable
        research result.  Provider failures, truncated output, invalid artifacts,
        derivation failures, and failed training plans remain visible in the ledger
        but consume only technical-attempt accounting.
        """

        receipt = self.ledger.receipt(plan["plan_id"])
        if plan["kind"] != "strategic_decision":
            return bool(receipt is not None and receipt.get("status") == "completed")
        if receipt is None or receipt.get("status") != "completed":
            return False
        report = self.ledger.report(plan["plan_id"])
        decision = (report or {}).get("result", {}).get("decision")
        action = decision.get("action") if isinstance(decision, dict) else None
        if action in {"wait", "request_human"}:
            return True

        queue = [child["plan_id"] for child in children.get(plan["plan_id"], [])]
        seen: set[str] = set()
        while queue:
            candidate_id = queue.pop()
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            candidate = plans.get(candidate_id)
            if candidate is None or candidate["kind"] == "strategic_decision":
                continue
            candidate_receipt = self.ledger.receipt(candidate_id)
            candidate_report = self.ledger.report(candidate_id)
            if self._durable_research_result(
                candidate,
                candidate_receipt,
                candidate_report,
                children=children,
            ):
                return True
            queue.extend(child["plan_id"] for child in children.get(candidate_id, []))
        return False

    @staticmethod
    def _durable_research_result(
        plan: dict[str, Any],
        receipt: dict[str, Any] | None,
        report: dict[str, Any] | None,
        *,
        children: dict[str, list[dict[str, Any]]],
    ) -> bool:
        if receipt is None or receipt.get("status") != "completed":
            return False
        result = report.get("result") if isinstance(report, dict) else None
        if plan["kind"] in {"phase_block", "cortex_block"}:
            return bool(
                isinstance(result, dict)
                and result.get("status", "completed") in {"completed", "simulated"}
                and isinstance(result.get("checkpoint_after"), str)
                and result["checkpoint_after"]
            )
        if plan["kind"] == "trainer_session":
            return isinstance(result, dict) and result.get("status") in {
                "completed",
                "simulated",
            }
        if plan["kind"] == "executor_job":
            workflow = plan.get("payload", {}).get("workflow")
            if isinstance(workflow, dict) and workflow.get("type") in {
                "cortex_train",
                "cortex_curriculum",
                "msm_trainer",
            }:
                # A proposal for weight-changing work is plumbing until its derived
                # training child succeeds.
                return False
            return bool(isinstance(result, dict) and result.get("valid", True))
        return False

    @staticmethod
    def _objective_complete(
        plan: dict[str, Any],
        report: dict[str, Any] | None,
    ) -> bool:
        if plan["kind"] != "phase_block" or report is None:
            return False
        result = report.get("result")
        return isinstance(result, dict) and result.get("gate_status") == "met"

    @staticmethod
    def _instructions(
        state: dict[str, Any],
        trigger_plan_id: str,
        remaining: dict[str, int],
        derivation_failure: dict[str, Any] | None = None,
        *,
        development_state: dict[str, Any] | None = None,
        review_only: bool = False,
    ) -> str:
        cortex_instructions = ""
        if (
            state["allowed_child_kinds"] == ["executor_job"]
            and not state["allowed_phase_ids"]
        ):
            cortex_instructions = (
                "\n\nThis is a Cortex 1.2B MSM campaign. The only weight-changing path is "
                "an executor_job whose workflow.type is cortex_train or cortex_curriculum; "
                "the supervisor will "
                "validate the executor-authored script and create the separately authorized "
                "cortex_block. Read checkpoint_after from the terminal trigger report and "
                "use it verbatim as workflow.parent_checkpoint. When the terminal trigger is "
                "a cortex_evaluation, checkpoint_after is the deterministic certificate's "
                "recommended parent: an admitted or developmental-progress candidate, "
                "otherwise its rollback parent. Developmental progress is a continuation "
                "seed, never a campaign winner. "
                "If a legacy review or blocked executor trigger has no checkpoint_after, "
                "use development_state.current_checkpoint verbatim as the parent; do not "
                "invent or recover a checkpoint from prose. "
                "Inspect evaluation.certificate, held-out transcripts, protected scores, "
                "pathological-output rate, and activation health. Loss is technical telemetry "
                "only: finite loss says optimization executed and non-finite loss says the run "
                "was numerically invalid. Never use loss magnitude or direction to rank a "
                "checkpoint, judge learning, trigger rollback, declare recovery, or select the "
                "next teaching strategy. Use a unique lowercase "
                "boundary-derived session_id, output checkpoint below core/cortex/, and "
                "artifact path below training/pipeline/msm/proposals/. For a small one-shot "
                "script, the workflow object must contain exactly type, session_id, "
                "parent_checkpoint, output_checkpoint, runner_args, and artifact_path. "
                "For a curriculum too large for one response, use type cortex_curriculum "
                "with exactly session_id, parent_checkpoint, output_checkpoint, runner_args, "
                "artifact_root, target_examples, chunk_examples, and concept. Set "
                "chunk_examples no higher than 50 and normally keep the total at no more "
                "than 200 append steps. An operator-requested foundation-style allowlist "
                "continuation may instead commission exactly one prepared 500-example "
                "block when the campaign context contains its immutable manifest and block "
                "artifact; preserve that block's source examples rather than inventing a "
                "replacement curriculum. The worker durably saves every accepted chunk, resumes at "
                "the first missing chunk after interruption, and retries each chunk before "
                "the executor ladder escalates; a failed append is not a failed curriculum. "
                "For this workflow, task.allowed_artifact_paths and artifact_json_schemas "
                "start empty and context_files includes "
                "training/pipeline/cortex/curriculum_chunk_schema.json; the worker derives "
                "each chunk artifact path and schema mapping. Request Qwen 3.6 TurboQuant "
                "(model_id qwen3.6-35b-a3b-q4-k-m-turboquant), max_model_attempts 5, and "
                "required_context_tokens 0. The executor harness owns the fixed escalation "
                "ladder DeepSeek V4 Flash -> Qwen TurboQuant -> Bonsai -> Gemma -> "
                "DeepSeek V4 Pro when the official DeepSeek credential is available "
                "and applies five attempts independently at each rung and append step; do not create "
                "a strategic boundary merely to select a fallback. Cap task.max_tokens at "
                "4096. The task object must contain "
                "job_id, title, instructions, allowed_artifact_paths, allowed_actions, "
                "max_tokens, context_files, and artifact_json_schemas; use instructions, "
                "not prompt, for the executor request. allowed_artifact_paths must contain "
                "only workflow.artifact_path, allowed_actions must be "
                "[\"VALIDATE_JSON\", \"RETURN_VALIDATION_ERRORS\"], and "
                "artifact_json_schemas must map workflow.artifact_path to "
                "training/pipeline/script_schema.json. Request exactly one msm_script_v1 "
                "JSON-object artifact and include that schema plus only the smallest "
                "relevant evidence files in task.context_files. Keep each "
                "teaching answer below 256 UTF-8 bytes. Use one epoch, batch size 1, "
                "learning rate 0.0002, ingress cuda:0, core cuda:1, local-files-only, and "
                "a short probe. When the latest deterministic decision specifically "
                "identifies expression-bridge collapse after foundational readiness, use --train-scope "
                "expression_bridge so the Ninereeds core and ingress projector remain "
                "unchanged; otherwise leave the default full scope. Never place --parent "
                "in runner_args; parent_checkpoint is "
                "the single authoritative parent and the supervisor adds the runner option. "
                "Use the exact option --lr for learning rate. The only commissioned probe "
                "option is --probe-max-new-tokens; --learning-rate and --probe-prompt do "
                "not exist. Executor task context_files run on the trainbox and therefore "
                "must use tracked training/, training_data/, or training_material/ evidence; "
                "never put workstation-local training/logs/ campaign artifacts there. "
                "Summarize relevant campaign evidence directly in task.instructions instead. "
                "Do not use phase_block, the retired 25M checkpoints, "
                "bootstrap fixtures, executor-controlled checkpoint promotion, multi-block continuation, or "
                "material unsupported by repository evidence. After foundational readiness, "
                "prefer a small coherent concept/contrast block and inspect behavioral probes, "
                "ownership, and resource metrics before choosing the next one. Checkpoint "
                "admission is owned only by "
                "the deterministic cortex_evaluation child created after every live block.\n\n"
            )
            if (
                isinstance(development_state, dict)
                and development_state.get("stage") == "foundational_bootstrap"
            ):
                lexical = development_state["evidence"].get(
                    "lexical_exposure", {}
                )
                cortex_instructions += (
                    "\n\nAUTHORITATIVE DEVELOPMENTAL STATE: foundational_bootstrap. "
                    f"The current learned lineage has only "
                    f"{development_state['evidence']['full_core_optimizer_steps']} full-core "
                    "optimizer steps. Its documented curriculum exposure contains "
                    f"{lexical.get('unique_surface_word_types', 0)} unique surface word "
                    f"types across {lexical.get('documented_examples', 0)} examples; "
                    f"language mix by example is "
                    f"{json.dumps(lexical.get('language_mix', {}), sort_keys=True)}. "
                    "Treat absent or weakly represented vocabulary and languages as an "
                    "exposure limitation, not evidence that a learned mapping failed. "
                    "Coherent chat is not expected yet. Behavioral collapse "
                    "must be measured but is not by itself grounds for rollback. Continue from "
                    "the certificate's recommended developmental parent with --train-scope full. "
                    "The deterministic controller owns 500-example foundational replay blocks "
                    "with a 65% replay / 25% new / 10% boundary-and-multilingual mix until the "
                    "10,000-example readiness floor. Do not prescribe or commission another "
                    "six-item block, tiny single-concept repair, or expression_bridge-only "
                    "block. Evaluate trends in prompt sensitivity, retention, response-form "
                    "diversity, representation separation, and activation health "
                    "relative to cumulative lexical and language exposure. A developmental "
                    "checkpoint must not be described as admitted, promoted, or a winner."
                )
            if state.get("regime") == "play":
                play = state["play"]
                branch = play["active_branch"]
                required_steps = CampaignController._prepared_play_block_steps(state)
                remaining_steps = max(
                    0,
                    int(play["branch_target_steps"]) - int(branch["optimizer_steps"]),
                )
                strategy = branch["strategy"]
                named_branch = (
                    re.search(r"\bbranch\s+0*([1-9][0-9]*)\b", strategy, re.IGNORECASE)
                    if isinstance(strategy, str)
                    else None
                )
                if (
                    named_branch is not None
                    and int(named_branch.group(1)) != branch["branch_index"]
                ):
                    strategy = (
                        "stale mislabeled strategy ignored; restate a coherent strategy "
                        "for the active branch from its actual lineage and evidence"
                    )
                cortex_instructions += (
                    "\n\nAUTHORITATIVE PLAY REGIME. One campaign is one research question, "
                    "not one path to victory. Its objective is new insight about the model, "
                    "not a successful score. The campaign must run multiple documented "
                    "strategy branches. Scores are instruments: target_score is an "
                    "aspirational branch milestone, not a campaign termination condition or "
                    "the sole ranking criterion. Within the active branch, continue "
                    "sequentially from play.current_checkpoint until the branch reaches its "
                    "optimizer-step horizon or target milestone; never reset to the baseline "
                    "after an ordinary behavioral regression. Evaluation after each block "
                    "is trajectory telemetry, not a one-lesson veto. Abandon a branch early "
                    "only for deterministic structural failure such as non-finite loss, dead "
                    "or saturated core layers, or an invalid checkpoint. The preserved "
                    "baseline is used only when the deterministic controller opens the next "
                    "branch. Each new branch must try a meaningfully different method or mix "
                    "of methods, state a falsifiable hypothesis in its executor title, and "
                    "use earlier observations to create a deliberate contrast or follow-up. "
                    "Keep experimental entropy high: explore genuinely separated settings "
                    "across ordering, dependency staging, contrast density, identity "
                    "reinforcement cadence, replay mix, optimizer dynamics, curriculum "
                    "interleaving, and deliberately odd but structurally safe combinations. "
                    "Include both clean single-variable contrasts and chaotic mixed-method "
                    "branches; do not spend the branch budget on timid neighboring settings. "
                    "Record valleys, recoveries, reversals, representation drift, output "
                    "quirks, contradictions, regularities, absurdities, and surprises; a "
                    "losing branch is data. Reaching target_score completes and documents "
                    "that branch, then opens another while research budget remains. Prefer "
                    "information gain and interpretable contrasts; best score is only one "
                    "reported axis and must not dominate branch selection. Treat branches "
                    "as experimental-evolution lineages, recipes as mutations, mixed methods "
                    "as recombination, evaluations as phenotype observations, and the durable "
                    "archive as the fossil record. Preserve strange low-scoring lineages when "
                    "they expose a possible mechanism. Before proposing a healthy training "
                    "boundary, explicitly answer four questions in the rationale and executor "
                    "instructions: (1) what is the active branch's hypothesis, (2) what exact "
                    "experimental variable or reproducible recipe is being tested, (3) how is "
                    "it scientifically distinct from completed branches and earlier blocks in "
                    "this branch, and (4) what next observation would support, contradict, or "
                    "complicate the hypothesis? Contract repair, switching cortex_train to "
                    "cortex_curriculum, changing chunk size, or retrying serialization is "
                    "plumbing, not experimental entropy. Do not copy a title, hypothesis, or "
                    "branch number from another lineage. Within a branch, preserve a coherent "
                    "method unless the latest evidence motivates a named mutation; between "
                    "branches, require a substantial recipe contrast. "
                    f"Active branch: {branch['branch_id']}; strategy: "
                    f"{strategy or 'choose and state one coherent strategy now'}; "
                    f"authoritative parent: {branch['current_checkpoint']}; progress: "
                    f"{branch['optimizer_steps']} / {play['branch_target_steps']} optimizer "
                    f"steps; completed branches: {len(play['completed_branches'])} / "
                    f"{play['max_branches']}; preserved baseline checkpoint: "
                    f"{play['baseline_checkpoint']}; remaining branch capacity: "
                    f"{remaining_steps} optimizer steps"
                    f"{f'; required prepared block size: {required_steps} examples/steps' if required_steps is not None else ''}; "
                    f"reference score: {float(play['target_score']):.1%}; "
                    f"best observed score: {float(play['best_score']):.1%}. Use the branch "
                    "ID in session, job, artifact, and checkpoint identities. Commission a "
                    "complete prepared word-training block using the established bootstrap "
                    "script/curriculum mechanics; do not turn Play into a one-item probe or "
                    "an image-training campaign. If a governance directive requires a "
                    "revised executable multi-lineage plan, satisfy it by emitting the next "
                    "bounded executor_job for the active controller-supplied branch; the "
                    "controller-provided preserved baseline checkpoint is authoritative and "
                    "does not require another human confirmation. Do not request a separate "
                    "non-weight-changing plan artifact just to restate the campaign plan."
                )
        repair_instructions = ""
        if derivation_failure is not None:
            repair_instructions = (
                "\n\nThe terminal trigger is an executor job whose required deterministic "
                "Cortex child was not created. This is a child-derivation failure, not a "
                "training result and not pending validation. Do not wait for another report. "
                f"The durable failure is {derivation_failure['error_type']}: "
                f"{derivation_failure['message']}\n"
                "Inspect the trigger plan and executor report, then propose exactly one "
                "corrected Cortex executor_job. Resume from the trigger workflow's "
                "parent_checkpoint because no new weights were written. Use fresh unique "
                "session, artifact, job, and output-checkpoint identifiers. Correct the "
                "reported contract error while preserving the smallest evidence-backed "
                "teaching intent. If the executor result contains failure_report, explicitly "
                "consider its attempt history, failure causes, and recommended action before "
                "choosing the correction. Full-ladder exhaustion is rare evidence deserving "
                "special attention, but it is not by itself a reason to request a human. "
                "Request human review only if a bounded correction cannot be made safely."
            )
        review_instructions = ""
        if review_only:
            autonomous_synthesis = (
                state["mode"] == "live"
                and state["allowed_child_kinds"] == ["executor_job"]
                and not state["allowed_phase_ids"]
            )
            if autonomous_synthesis:
                review_instructions = (
                    "\n\nThis bounded campaign has reached its budget or time window. "
                    "Perform a fresh read-only research synthesis from the evaluations, "
                    "transcripts, MRI, representation map, atlas, developmental state, and "
                    "north-star goal. Return action=wait, child_plan_json=null, and "
                    "user_message=null. Put the predecessor research memo in rationale: "
                    "state what was learned, identify the certified continuation checkpoint, "
                    "propose one or more plausible next experimental directions, and explain "
                    "the tradeoffs. The evaluator's recommended_next_action and the prior "
                    "campaign objective are advisory hypotheses, not binding instructions. "
                    "You may reject them when the evidence supports a better bounded move. "
                    "Do not request a human merely because the campaign ended."
                )
            else:
                review_instructions = (
                "\n\nThe campaign deadline or all weight-changing and executor child budgets "
                "have been reached. This is "
                "the final read-only campaign review, not another experiment. Inspect the "
                "latest deterministic evaluation and campaign evidence. Return "
                "action=request_human with no child plan. The user_message must state whether "
                "a winner was admitted, identify the exact admitted or rollback seed, explain "
                "the dominant failure mode, and propose one bounded next campaign objective "
                    "that directly tests the evaluator's recommended next action. "
                    "Treat that recommendation as evidence, not an order; explain any "
                    "better-supported alternative."
                )
        governance_directive = state.get("governance", {}).get("pending_directive")
        governance_instructions = (
            "\n\nBINDING GOVERNANCE DIRECTIVE. " + governance_directive
            if isinstance(governance_directive, str) and governance_directive
            else ""
        )
        return (
            f"Campaign objective: {state['objective']}\n\n"
            f"The terminal trigger is {trigger_plan_id}; its complete plan and report are "
            "included in this boundary envelope. Choose exactly one bounded next action. "
            "Prefer the smallest diagnostic or dose adjustment justified by the latest "
            "metrics. Never advance to another phase unless the current phase gate is met; "
            "the deterministic campaign controller will stop automatically when it observes "
            "gate_status=met.\n\n"
            "For a phase_block child, payload must contain exactly phase_id, runner_args, "
            "and continuation. runner_args is a JSON array of existing msm_phase_runner "
            "options; use the latest checkpoint_after as --parent, cuda:1 as --device, and "
            "keep continuation.remaining_blocks within the supplied constraint. Phase "
            "blocks are the only commissioned path that changes Ninereeds weights.\n\n"
            "For an executor_job child, payload must contain task, model_id, "
            "required_context_tokens, max_model_attempts, and optional workflow. Executor "
            "jobs are read/propose-only and cannot themselves update weights.\n\n"
            f"{cortex_instructions}"
            f"{repair_instructions}"
            f"{review_instructions}\n\n"
            f"{governance_instructions}\n\n"
            f"Remaining campaign budgets before this boundary: {json.dumps(remaining, sort_keys=True)}"
        )

    def _review_context_files(self, state: dict[str, Any]) -> list[str]:
        result = list(state["context_files"])
        registry_path = self.repo_root / "training/logs/campaign_registry.json"
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return result
        entry = next(
            (
                row
                for row in registry.get("campaigns", [])
                if isinstance(row, dict)
                and row.get("campaign_id") == state["campaign_id"]
            ),
            None,
        )
        if entry is None or not isinstance(entry.get("artifact_root"), str):
            return result
        for name in (
            "decision.json",
            "01_report.md",
            "metrics.json",
            "cortex_mri.html",
            "cortex_3d_map.html",
            "cortex_atlas.html",
        ):
            relative = f"{entry['artifact_root'].rstrip('/')}/{name}"
            path = (self.repo_root / relative).resolve()
            if (
                self.repo_root in path.parents
                and path.is_file()
                and relative not in result
            ):
                result.append(relative)
        return result[:32]
