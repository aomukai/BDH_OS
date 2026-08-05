from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .campaign_controller import CampaignController
from .emergency_recovery import EmergencyRecoveryPolicy
from .ledger import utc_now
from .provider_failover import ProviderError, ProviderRouter


class AdversarialReviewError(RuntimeError):
    pass


class AdversarialReviewPolicy:
    """Stateless dialectical review over committed teaching mutations."""

    def __init__(
        self,
        control_root: Path,
        *,
        repo_root: Path,
        router: ProviderRouter,
        sol_policy: EmergencyRecoveryPolicy,
        mutation_interval: int = 5,
    ) -> None:
        if mutation_interval < 1:
            raise ValueError("mutation_interval must be positive")
        self.control_root = control_root.resolve()
        self.repo_root = repo_root.resolve()
        self.router = router
        self.sol_policy = sol_policy
        self.mutation_interval = mutation_interval
        self.reviews_dir = self.control_root / "campaign/governance/reviews"
        self.schemas = {
            "critique": self.repo_root / "training/pipeline/adversarial_critique_schema.json",
            "defence": self.repo_root / "training/pipeline/adversarial_defence_schema.json",
            "verdict": self.repo_root / "training/pipeline/adversarial_verdict_schema.json",
        }

    def maybe_review(
        self,
        controller: CampaignController,
    ) -> dict[str, Any]:
        state = controller.store.read()
        if state is None or state["status"] != "running":
            return {"action": "none"}
        mutations = self._mutations(controller, state)
        previous = int(state["governance"]["last_reviewed_mutations"])
        if len(mutations) - previous < self.mutation_interval:
            return {
                "action": "not_due",
                "mutations": len(mutations),
                "next_at": previous + self.mutation_interval,
            }

        # A campaign upgraded in place receives one review of its latest tranche;
        # historical mutations are not replayed into a costly governance backlog.
        review_count = (
            len(mutations)
            if previous == 0
            else previous + self.mutation_interval
        )
        review_id = f"{state['campaign_id']}-advocatus-{review_count:04d}"
        path = self.reviews_dir / f"{review_id}.json"
        supersedes_review_id = None
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            invalid = next(
                (
                    error
                    for role in ("critique", "defence", "verdict")
                    if (
                        error := self._policy_error(
                            role,
                            existing.get(role)
                            if isinstance(existing.get(role), dict)
                            else {},
                        )
                    )
                ),
                None,
            )
            if invalid is None:
                controller.record_governance_review(
                    review_id=review_id,
                    mutation_count=review_count,
                )
                return {"action": "already_reviewed", "review_id": review_id}
            supersedes_review_id = review_id
            review_id += "-policy-retry-01"
            path = self.reviews_dir / f"{review_id}.json"

        evidence = mutations[review_count - self.mutation_interval:review_count]
        public_evidence = [item["public"] for item in evidence]
        private_rationales = [item["private_rationale"] for item in evidence]
        try:
            critique_call = self._run_stage(
                self._critique_prompt(state, public_evidence),
                self.schemas["critique"],
                role="critique",
            )
            defence_call = self._run_stage(
                self._defence_prompt(
                    state,
                    public_evidence,
                    private_rationales,
                    critique_call.output,
                ),
                self.schemas["defence"],
                role="defence",
            )
            verdict_call = self._run_stage(
                self._verdict_prompt(
                    public_evidence,
                    critique_call.output,
                    defence_call.output,
                ),
                self.schemas["verdict"],
                role="verdict",
            )
        except (ProviderError, AdversarialReviewError) as exc:
            failure_id = (
                f"{review_id}-technical-"
                + utc_now().replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")
            )
            failure_path = self.reviews_dir / f"{failure_id}.json"
            self._write(
                failure_path,
                {
                    "schema_version": "ninereeds_adversarial_review_attempt_v1",
                    "review_id": failure_id,
                    "campaign_id": state["campaign_id"],
                    "created_at": utc_now(),
                    "status": "technical_failure",
                    "error": str(exc)[:4000],
                    "evidence": public_evidence,
                    "research_budget_charged": False,
                },
            )
            return {
                "action": "technical_failure",
                "error": str(exc)[:1000],
                "report": str(failure_path),
            }

        report = {
            "schema_version": "ninereeds_adversarial_review_v1",
            "review_id": review_id,
            "supersedes_review_id": supersedes_review_id,
            "campaign_id": state["campaign_id"],
            "created_at": utc_now(),
            "reviewed_mutation_count": review_count,
            "mutation_interval": self.mutation_interval,
            "evidence": public_evidence,
            "critique": critique_call.output,
            "defence": defence_call.output,
            "verdict": verdict_call.output,
            "calls": [
                self._call_attribution("critique", critique_call),
                self._call_attribution("defence", defence_call),
                self._call_attribution("verdict", verdict_call),
            ],
            "sol_adjudication": None,
        }
        self._write(path, report)
        controller.record_governance_review(
            review_id=review_id,
            mutation_count=review_count,
        )
        if verdict_call.output.get("verdict") == "approve":
            return {"action": "approved", "review_id": review_id, "report": str(path)}

        incident = {
            "schema_version": "ninereeds_orchestrator_incident_v1",
            "incident_type": "adversarial_review",
            "errors": [],
            "campaign": {
                "campaign_id": state["campaign_id"],
                "status": state["status"],
                "objective": state["objective"],
                "usage": state["usage"],
                "budgets": state["budgets"],
            },
            "current": None,
            "adversarial_review": report,
        }
        adjudication = self.sol_policy.handle(
            incident,
            campaign_controller=controller,
        )
        report["sol_adjudication"] = adjudication
        self._write(path, report)
        return {
            "action": "rejected_adjudicated",
            "review_id": review_id,
            "report": str(path),
            "sol": adjudication,
        }

    def _mutations(
        self,
        controller: CampaignController,
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        plans = controller._plans()
        root = state.get("root_boundary_plan_id")
        if not isinstance(root, str):
            return []
        descendants: dict[str, list[dict[str, Any]]] = {}
        for candidate in plans.values():
            parent = candidate.get("parent_plan_id")
            if isinstance(parent, str):
                descendants.setdefault(parent, []).append(candidate)
        lineage: set[str] = set()
        queue = [root]
        while queue:
            plan_id = queue.pop()
            if plan_id in lineage:
                continue
            lineage.add(plan_id)
            queue.extend(item["plan_id"] for item in descendants.get(plan_id, []))

        values = []
        for plan_id in lineage:
            plan = plans.get(plan_id)
            if plan is None or plan["kind"] not in {"cortex_block", "phase_block"}:
                continue
            receipt = controller.ledger.receipt(plan_id)
            report = controller.ledger.report(plan_id)
            result = report.get("result") if isinstance(report, dict) else None
            if (
                receipt is None
                or receipt.get("status") != "completed"
                or not isinstance(result, dict)
                or not isinstance(result.get("checkpoint_after"), str)
            ):
                continue
            boundary = self._ancestor_boundary(plan, plans)
            evaluation = next(
                (
                    child
                    for child in descendants.get(plan_id, [])
                    if child["kind"] == "cortex_evaluation"
                    and (controller.ledger.receipt(child["plan_id"]) or {}).get("status")
                    == "completed"
                ),
                None,
            )
            evaluation_report = (
                controller.ledger.report(evaluation["plan_id"])
                if isinstance(evaluation, dict)
                else None
            )
            payload = plan.get("payload", {})
            script = payload.get("script") if isinstance(payload, dict) else None
            public = {
                "plan_id": plan_id,
                "created_at": plan["created_at"],
                "kind": plan["kind"],
                "checkpoint_after": result["checkpoint_after"],
                "teaching": {
                    "concept": script.get("concept") if isinstance(script, dict) else payload.get("concept"),
                    "examples": len(script.get("items", [])) if isinstance(script, dict) else result.get("metadata", {}).get("examples"),
                    "source": payload.get("jsonl_path") or payload.get("jsonl_paths"),
                    "runner_args": payload.get("runner_args"),
                },
                "behavioral_observation": self._without_loss(
                    (evaluation_report or {}).get("result", {}).get("certificate")
                ),
            }
            rationale = None
            if boundary is not None:
                boundary_report = controller.ledger.report(boundary["plan_id"])
                decision = (boundary_report or {}).get("result", {}).get("decision")
                rationale = decision.get("rationale") if isinstance(decision, dict) else None
            values.append({"public": public, "private_rationale": rationale})
        values.sort(key=lambda item: (item["public"]["created_at"], item["public"]["plan_id"]))
        return values

    @staticmethod
    def _ancestor_boundary(
        plan: dict[str, Any],
        plans: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        cursor = plan
        seen: set[str] = set()
        while isinstance(cursor, dict) and cursor["plan_id"] not in seen:
            seen.add(cursor["plan_id"])
            if cursor["kind"] == "strategic_decision":
                return cursor
            parent = cursor.get("parent_plan_id")
            cursor = plans.get(parent) if isinstance(parent, str) else None
        return None

    @classmethod
    def _without_loss(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: cls._without_loss(item)
                for key, item in value.items()
                if "loss" not in key.casefold()
            }
        if isinstance(value, list):
            return [cls._without_loss(item) for item in value]
        return value

    @staticmethod
    def _critique_prompt(state: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
        return (
            "You are advocatus diaboli. Review only what the strategist taught and what "
            "was behaviorally observed; you are intentionally not given its rationale. "
            "Challenge repetition, disguised retries, weak experimental contrast, unfalsifiable "
            "mutations, ancestry errors, and sequences that generate no new information. "
            "Regression, chaos, valleys, behavioral stasis, and low scores are valid research "
            "outcomes and are not failures. Never demand improvement, rollback, abandonment, or "
            "branching merely because behavior regressed or a score stayed flat. Loss is absent "
            "because it is technical telemetry only. Ask why repeated "
            "choices were necessary, then either approve or challenge.\n\n"
            + json.dumps({"objective": state["objective"], "actions": evidence}, ensure_ascii=False, indent=2)
        )

    @staticmethod
    def _defence_prompt(
        state: dict[str, Any],
        evidence: list[dict[str, Any]],
        rationales: list[Any],
        critique: dict[str, Any],
    ) -> str:
        return (
            "You are the stateless strategic orchestrator answering an adversarial review. "
            "Address every question directly. Explain or defend repeated teaching choices using "
            "the campaign objective and recorded rationale, or accept the criticism and propose "
            "a materially different next approach. Do not concede merely because scores stayed "
            "flat or behavior regressed: this campaign explicitly studies valleys and recovery. "
            "Do not use loss as evidence of model quality.\n\n"
            + json.dumps(
                {
                    "objective": state["objective"],
                    "actions": evidence,
                    "recorded_rationales": rationales,
                    "critique": critique,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    @staticmethod
    def _verdict_prompt(
        evidence: list[dict[str, Any]],
        critique: dict[str, Any],
        defence: dict[str, Any],
    ) -> str:
        return (
            "You are advocatus diaboli issuing the final verdict. Determine whether the "
            "orchestrator answered every material objection and whether continuing the strategy "
            "is likely to produce new information. Approve coherent intentional repetition; "
            "reject unanswered objections or cosmetic variation. Model regression, behavioral "
            "stasis, and low scores are not reasons to reject or prescribe rollback/branching. "
            "An approve verdict is an unconditional green light and therefore must have an empty "
            "required_changes list; use reject when changes remain required. Loss must not be "
            "considered.\n\n"
            + json.dumps(
                {"actions": evidence, "critique": critique, "defence": defence},
                ensure_ascii=False,
                indent=2,
            )
        )

    @staticmethod
    def _call_attribution(role: str, execution: Any) -> dict[str, Any]:
        return {
            "role": role,
            "provider": execution.provider,
            "model": execution.model,
            "duration_seconds": execution.duration_seconds,
            "failover_reason": execution.failover_reason,
        }

    def _run_stage(
        self,
        prompt: str,
        schema: Path,
        *,
        role: str,
    ) -> Any:
        correction = ""
        last_error = ""
        for _attempt in range(2):
            execution = self.router.run(prompt + correction, schema)
            last_error = self._policy_error(role, execution.output) or ""
            if not last_error:
                return execution
            correction = (
                "\n\nYOUR PREVIOUS OUTPUT VIOLATED GOVERNANCE POLICY: "
                + last_error
                + ". Return a corrected schema-bound answer. Do not optimize for score, "
                "improvement, or recovery speed; evaluate experimental coherence and "
                "information value only."
            )
        raise AdversarialReviewError(
            f"{role} violated governance policy twice: {last_error}"
        )

    @staticmethod
    def _policy_error(role: str, output: dict[str, Any]) -> str | None:
        text = json.dumps(output, ensure_ascii=False).casefold()
        if "loss" in text:
            return "loss may not appear in adversarial research judgment"
        forbidden = (
            r"score[^.]{0,80}(?:stuck|stagnat|did not change|does not change)[^.]{0,80}(?:indicat|therefore|no new information|should|must|will|pivot)",
            r"(?:after|because of|following) (?:any )?(?:behavioral )?(?:regression|plateau)[^.]{0,100}(?:rollback|branch|abandon|stop)",
            r"(?:regress|plateau)[^.]{0,80}(?:is|was) (?:a )?(?:failure|mistake)",
            r"last healthy checkpoint",
        )
        if any(re.search(pattern, text) for pattern in forbidden):
            return (
                "behavioral regression, stasis, or score direction may not be treated "
                "as failure or as grounds for rollback, branching, or abandonment"
            )
        if (
            role == "verdict"
            and output.get("verdict") == "approve"
            and output.get("required_changes")
        ):
            return "approve must be an unconditional green light with no required changes"
        return None

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
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
