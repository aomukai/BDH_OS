from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab.backend.config import LabConfig
from lab.backend.messages.store import MessageStore

from .ledger import ControlLedger, LedgerError, TERMINAL_RECEIPT_STATUSES, utc_now


CAMPAIGN_SCHEMA = "ninereeds_autonomous_campaign_v1"
CAMPAIGN_STATUSES = {"running", "waiting", "paused", "completed", "blocked"}
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
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def read(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignError(f"cannot read campaign state: {exc}") from exc
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
        }
        if not isinstance(state, dict) or set(state) != expected:
            raise CampaignError("campaign state fields do not match v1")
        if state["schema_version"] != CAMPAIGN_SCHEMA:
            raise CampaignError("invalid campaign schema_version")
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
        if not 1 <= state["budgets"]["strategic_boundaries"] <= 100:
            raise CampaignError("strategic boundary budget must be from 1 through 100")
        if any(value > 100 for value in state["budgets"].values()):
            raise CampaignError("campaign budget may not exceed 100")
        if state["stop_reason"] is not None and not isinstance(state["stop_reason"], str):
            raise CampaignError("stop_reason must be a string or null")
        history = state["history"]
        if not isinstance(history, list) or len(history) > 100:
            raise CampaignError("campaign history is invalid")


class CampaignController:
    def __init__(
        self,
        ledger: ControlLedger,
        *,
        repo_root: Path,
        store: CampaignStateStore | None = None,
        message_store: MessageStore | None = None,
        controller_id: str = "campaign-controller",
    ) -> None:
        self.ledger = ledger
        self.repo_root = repo_root.resolve()
        self.store = store or CampaignStateStore(ledger.root)
        self.message_store = message_store or MessageStore(LabConfig.from_env())
        self.controller_id = controller_id

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
            }
            self.store.write(state)
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

    def reconcile(self) -> dict[str, Any]:
        with self.store.locked() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.store.read()
            if state is None:
                return {"active": False, "action": "none"}
            if state["status"] != "running":
                return {
                    "active": False,
                    "action": "none",
                    "status": state["status"],
                }
            if time.time() >= _parse_time(state["deadline_at"]):
                self._stop(
                    state,
                    "paused",
                    "Campaign wall-clock deadline reached.",
                    event="deadline",
                )
                return {"active": False, "action": "paused_deadline"}

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
            while children.get(current):
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
            if plan["kind"] == "strategic_decision":
                decision = (report or {}).get("result", {}).get("decision")
                action = decision.get("action") if isinstance(decision, dict) else None
                if action in {"wait", "request_human"}:
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

            if self._objective_complete(plan, report):
                self._stop(
                    state,
                    "completed",
                    f"Objective gate met by {current}.",
                    event="objective-complete",
                )
                return {"active": False, "action": "completed"}

            remaining = {
                key: state["budgets"][key] - usage[key]
                for key in state["budgets"]
            }
            if remaining["strategic_boundaries"] <= 0:
                self._stop(
                    state,
                    "paused",
                    "Strategic boundary budget exhausted.",
                    event="strategic-budget",
                )
                return {"active": False, "action": "paused_budget"}
            allowed = [
                kind
                for kind in state["allowed_child_kinds"]
                if remaining[COUNTED_KINDS[kind]] > 0
            ]
            if not allowed:
                self._stop(
                    state,
                    "paused",
                    "All allowed child-plan budgets are exhausted.",
                    event="child-budget",
                )
                return {"active": False, "action": "paused_budget"}

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
            strategic = self.ledger.create_plan(
                kind="strategic_decision",
                mode=state["mode"],
                payload={
                    "boundary_id": boundary_id,
                    "title": (
                        f"{state['campaign_id']} boundary {boundary_index}: choose next action"
                    ),
                    "instructions": self._instructions(state, current, remaining),
                    "context_files": state["context_files"],
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
                            f"Created strategic boundary {strategic['plan_id']} after {current}."
                        ),
                    }
                ]
            )[-100:]
            self.store.write(state)
            return {
                "active": True,
                "action": "created_strategic_boundary",
                "plan_id": strategic["plan_id"],
            }

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
            state["status"] = status
            state["stop_reason"] = None if status == "running" else reason
            state["updated_at"] = utc_now()
            state["history"] = (
                state["history"]
                + [{"at": state["updated_at"], "status": status, "detail": reason}]
            )[-100:]
            self.store.write(state)
            return state

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
            kind = plans[plan_id]["kind"]
            key = COUNTED_KINDS.get(kind)
            if key is not None:
                usage[key] += 1
            queue.extend(child["plan_id"] for child in children.get(plan_id, []))
        return usage

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
    ) -> str:
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
            f"Remaining campaign budgets before this boundary: {json.dumps(remaining, sort_keys=True)}"
        )
