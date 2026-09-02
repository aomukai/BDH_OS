"""Schema-bound Sol decision for one durable research-lab activation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from typing import Any

from ..errors import RemoteJobError, SafetyError
from ..schema import load_schema, validate
from .contracts import _declaration, _object_file
from .visual_provider import ProviderFailure, _codex, _http


class ResearchDecisionHandler:
    ADVISOR_ROUTE_IDS = (
        "research-advisor-current",
        "research-advisor-established",
        "research-advisor-wildcard",
    )
    ADVICE_PROMPT_ID = "research-advice-v1"

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        prompt = context.get("prompt")
        if not prompt:
            raise SafetyError("research conductor has no configured prompt")
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        journal = self._materialize_campaign_journal(payload, context, run_root)
        stable_prefix = (
            prompt["system"].strip()
            + "\n\nTask contract:\n"
            + prompt["template"].strip()
        )
        task = self._activation_task(payload, journal)
        prompt_text = stable_prefix + "\n\nCurrent activation data:\n" + json.dumps(
            task, ensure_ascii=False, sort_keys=True,
        )
        release_root = Path(context["release_root"]).resolve()
        schema_path = (release_root / prompt["output_schema"]).resolve()
        schema = load_schema(release_root, prompt["output_schema"])
        initial_root = run_root / "conductor-initial"
        initial_root.mkdir()
        result, selected, attempts = self._call_conductor(
            context, prompt_text, schema_path, schema, initial_root,
            payload["allowed_actions"], phase="initial_decision",
        )
        advice_sampled = False
        continuation_prompt_text: str | None = None
        if result["action"]["kind"] == "ask_for_advice":
            advice_sampled = True
            advice_question = result["action"]["advice_question"]
            anonymous_advice, advisor_attempts = self._collect_advice(
                payload, context, task, advice_question, release_root, run_root,
            )
            attempts.extend(advisor_attempts)
            final_actions = [
                action for action in payload["allowed_actions"]
                if action != "ask_for_advice"
            ]
            if not final_actions:
                raise SafetyError("ask_for_advice left Sol with no executable decision")
            continuation_task = {
                **task,
                "allowed_actions": final_actions,
                "advice_question": advice_question,
                "anonymous_advice": anonymous_advice,
            }
            continuation_prompt_text = (
                stable_prefix
                + "\n\nDeliberation continuation:\n"
                + "You invoked ask_for_advice. Exactly three anonymous ideas are now "
                  "included below. They have zero authority and are not evidence. Their sources "
                  "are intentionally unavailable to you. Use or discard each idea freely, then "
                  "make one authoritative laboratory decision from allowed_actions. "
                  "ask_for_advice is no longer available in this decision cycle."
                + "\n\nCurrent activation data and anonymous ideas:\n"
                + json.dumps(continuation_task, ensure_ascii=False, sort_keys=True)
            )
            final_root = run_root / "conductor-final"
            final_root.mkdir()
            result, selected, final_attempts = self._call_conductor(
                context, continuation_prompt_text, schema_path, schema, final_root,
                final_actions, phase="final_decision",
            )
            attempts.extend(final_attempts)
        decision_document = {
            "schema_version": "ninereeds_research_decision_v1",
            "campaign_id": payload["campaign_id"],
            "campaign_number": payload["campaign_number"],
            "lab_id": payload["lab_id"],
            "activation_id": payload["activation_id"],
            "model_id": selected["id"],
            "model_exact_name": selected["exact_name"],
            "allowed_actions": payload["allowed_actions"],
            "observation": payload["observation"],
            "campaign_journal_sha256": payload["campaign_journal"]["sha256"],
            "advice_sampled": advice_sampled,
            **result,
        }
        decision_path, decision_sha, decision_size = _object_file(
            context["state_root"],
            (json.dumps(decision_document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        transcript_document = {
            "schema_version": "ninereeds_research_provider_transcript_v1",
            "activation_id": payload["activation_id"],
            "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "continuation_prompt_sha256": (
                hashlib.sha256(continuation_prompt_text.encode("utf-8")).hexdigest()
                if continuation_prompt_text is not None else None
            ),
            "advice_sampled": advice_sampled,
            "attempts": attempts,
        }
        transcript_path, transcript_sha, transcript_size = _object_file(
            context["state_root"],
            (json.dumps(transcript_document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        manifest = {
            "campaign_id": payload["campaign_id"],
            "lab_id": payload["lab_id"],
            "activation_id": payload["activation_id"],
            "action": result["action"]["kind"],
            "model_id": selected["id"],
            "advice_sampled": advice_sampled,
        }
        return {
            "status": "succeeded",
            "action": result["action"],
            "message": result["message"],
            "rationale": result["rationale"],
            "updated_todo": result["updated_todo"],
            "artifacts": [
                _declaration(
                    "research_decision", decision_path, decision_sha, decision_size,
                    {"schema_version": "ninereeds_research_decision_v1", **manifest},
                ),
                _declaration(
                    "provider_transcript", transcript_path, transcript_sha, transcript_size,
                    {"schema_version": "ninereeds_research_provider_transcript_v1", **manifest},
                ),
            ],
        }

    @staticmethod
    def _activation_task(
        payload: dict[str, Any], journal: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "lab_id": payload["lab_id"],
            "campaign_id": payload["campaign_id"],
            "campaign_number": payload["campaign_number"],
            "activation_id": payload["activation_id"],
            "goal": payload["goal"],
            "todo": payload["todo"],
            "observation": payload["observation"],
            "recent_reports": payload["recent_reports"],
            "available_datasets": payload["available_datasets"],
            "allowed_actions": payload["allowed_actions"],
            "campaign_journal": journal,
        }

    @staticmethod
    def _materialize_campaign_journal(
        payload: dict[str, Any], context: dict[str, Any], run_root: Path,
    ) -> dict[str, Any]:
        declaration = payload["campaign_journal"]
        state_root = Path(context["state_root"]).resolve()
        allowed_root = state_root / "research-journals"
        source = Path(declaration["uri"]).resolve()
        if source != allowed_root and allowed_root not in source.parents:
            raise SafetyError("campaign journal is outside the managed research-journals root")
        try:
            data = source.read_bytes()
        except OSError as exc:
            raise SafetyError(f"campaign journal is unavailable: {exc}") from exc
        if len(data) != int(declaration["byte_size"]):
            raise SafetyError("campaign journal byte size changed after decision creation")
        if hashlib.sha256(data).hexdigest() != declaration["sha256"]:
            raise SafetyError("campaign journal hash changed after decision creation")
        destination = run_root / "campaign-journal.md"
        destination.write_bytes(data)
        destination.chmod(0o444)
        return {
            "schema_version": declaration["schema_version"],
            "path": "../campaign-journal.md",
            "sha256": declaration["sha256"],
            "byte_size": declaration["byte_size"],
            "experiment_count": declaration["experiment_count"],
            "lookup": (
                "Before repeating or varying an intervention, use rg -n -i with its parameter, "
                "dataset, mechanism, or hypothesis terms against ../campaign-journal.md. Read only "
                "matching entries and follow provenance when verification is needed."
            ),
        }

    def _call_conductor(
        self, context: dict[str, Any], prompt_text: str, schema_path: Path,
        schema: dict[str, Any], run_root: Path, allowed_actions: list[str], *,
        phase: str,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        attempts: list[dict[str, Any]] = []
        result = None
        selected = None
        for index, model in enumerate(context["route_models"]):
            provider = context["providers"][model["provider"]]
            try:
                if not model["enabled"] or not provider["enabled"]:
                    raise ProviderFailure(
                        "research route contains a disabled model or provider",
                        "capability_transient",
                    )
                if provider["kind"] == "codex_cli":
                    value, transcript = _codex(
                        provider, model, prompt_text, schema_path, [], run_root,
                    )
                elif provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                    value, transcript = _http(
                        provider, model, prompt_text, context["route"]["max_total_tokens"],
                    )
                else:
                    raise ProviderFailure(
                        "unsupported research-conductor provider", "capability_transient",
                    )
                errors = validate(value, schema)
                if errors:
                    raise ProviderFailure(
                        "research decision failed schema validation: " + "; ".join(errors),
                        "repairable_output", "structured_response_invalid",
                    )
                self._validate_semantics(value, allowed_actions)
                result = value
                selected = model
                attempts.append({
                    "phase": phase,
                    "model_id": model["id"], "provider_id": provider["id"],
                    "status": "succeeded", "transcript": transcript,
                })
                break
            except ProviderFailure as exc:
                attempts.append({
                    "phase": phase,
                    "model_id": model["id"], "provider_id": provider["id"],
                    "status": "failed", "failure_class": exc.failure_class,
                    "failure_code": exc.code, "message": str(exc),
                    **({"transcript": exc.transcript} if exc.transcript is not None else {}),
                })
                if (
                    index + 1 >= len(context["route_models"])
                    or exc.failure_class not in context["route"]["fallback_failure_classes"]
                ):
                    break
        if result is None or selected is None:
            last = attempts[-1] if attempts else {}
            raise RemoteJobError(
                f"research conductor exhausted its Sol route during {phase}: "
                + last.get("message", "no provider attempt was recorded"),
                failure_class=last.get("failure_class", "capability_transient"),
                code=last.get("failure_code", "provider_capability_unavailable"),
            )
        return result, selected, attempts

    def _collect_advice(
        self, payload: dict[str, Any], context: dict[str, Any], task: dict[str, Any],
        question: str, release_root: Path, run_root: Path,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        advice_prompt = context.get("prompts", {}).get(self.ADVICE_PROMPT_ID)
        if not advice_prompt:
            raise SafetyError("research advice has no configured prompt")
        schema_path = (release_root / advice_prompt["output_schema"]).resolve()
        schema = load_schema(release_root, advice_prompt["output_schema"])
        advice_task = {
            "question": question,
            "campaign_goal": task["goal"],
            "current_todo": task["todo"],
            "observation": task["observation"],
            "recent_reports": task["recent_reports"],
            "available_datasets": task["available_datasets"],
        }
        prompt_text = (
            advice_prompt["system"].strip()
            + "\n\nTask contract:\n"
            + advice_prompt["template"].strip()
            + "\n\nExact question and evidence:\n"
            + json.dumps(advice_task, ensure_ascii=False, sort_keys=True)
        )
        calls: dict[str, Any] = {}
        with ThreadPoolExecutor(
            max_workers=len(self.ADVISOR_ROUTE_IDS),
            thread_name_prefix="research-advice",
        ) as pool:
            for route_id in self.ADVISOR_ROUTE_IDS:
                advisor_root = run_root / route_id
                advisor_root.mkdir()
                calls[route_id] = pool.submit(
                    self._call_advisor_route,
                    payload["activation_id"], context, route_id, prompt_text,
                    schema_path, schema, advisor_root,
                )
            results = {route_id: calls[route_id].result() for route_id in self.ADVISOR_ROUTE_IDS}
        selected_ids = [results[route_id][2] for route_id in self.ADVISOR_ROUTE_IDS]
        if len(set(selected_ids)) != 3:
            raise SafetyError("research advice did not use three distinct models")
        ideas = [results[route_id][0] for route_id in self.ADVISOR_ROUTE_IDS]
        presentation_order = sorted(
            range(3),
            key=lambda index: hashlib.sha256(
                f"{payload['activation_id']}:advice-presentation:{index}".encode("utf-8")
            ).hexdigest(),
        )
        anonymous = [ideas[index] for index in presentation_order]
        attempts: list[dict[str, Any]] = []
        for route_id in self.ADVISOR_ROUTE_IDS:
            attempts.extend(results[route_id][1])
        return anonymous, attempts

    def _call_advisor_route(
        self, activation_id: str, context: dict[str, Any], route_id: str,
        prompt_text: str, schema_path: Path, schema: dict[str, Any], run_root: Path,
    ) -> tuple[str, list[dict[str, Any]], str]:
        try:
            route = context["routes"][route_id]
            models = [context["models"][model_id] for model_id in route["ordered_model_ids"]]
        except KeyError as exc:
            raise SafetyError(f"research advice route is unavailable: {route_id}") from exc
        if not route["enabled"] or not models:
            raise SafetyError(f"research advice route is disabled or empty: {route_id}")
        offset = int(hashlib.sha256(
            f"{activation_id}:{route_id}".encode("utf-8")
        ).hexdigest(), 16) % len(models)
        candidates = models[offset:] + models[:offset]
        attempts: list[dict[str, Any]] = []
        for index, model in enumerate(candidates):
            provider = context["providers"][model["provider"]]
            try:
                if not model["enabled"] or not provider["enabled"]:
                    raise ProviderFailure(
                        "research advice route contains a disabled model or provider",
                        "capability_transient",
                    )
                if provider["kind"] != "codex_cli":
                    raise ProviderFailure(
                        "research advice requires an isolated headless Codex provider",
                        "deterministic_specification", "configuration_invalid",
                    )
                value, transcript = _codex(
                    provider, model, prompt_text, schema_path, [], run_root,
                    reasoning_effort="high",
                )
                errors = validate(value, schema)
                if errors:
                    raise ProviderFailure(
                        "research advice failed schema validation: " + "; ".join(errors),
                        "repairable_output", "structured_response_invalid",
                    )
                idea = value["idea"].strip()
                attempts.append({
                    "phase": "advice", "advisor_slot": route_id,
                    "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
                    "model_id": model["id"], "provider_id": provider["id"],
                    "reasoning_effort": "high", "status": "succeeded",
                    "transcript": transcript,
                })
                return idea, attempts, model["id"]
            except ProviderFailure as exc:
                attempts.append({
                    "phase": "advice", "advisor_slot": route_id,
                    "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
                    "model_id": model["id"], "provider_id": provider["id"],
                    "reasoning_effort": "high", "status": "failed",
                    "failure_class": exc.failure_class, "failure_code": exc.code,
                    "message": str(exc),
                    **({"transcript": exc.transcript} if exc.transcript is not None else {}),
                })
                if (
                    index + 1 >= len(candidates)
                    or exc.failure_class not in route["fallback_failure_classes"]
                ):
                    break
        last = attempts[-1] if attempts else {}
        raise RemoteJobError(
            f"research advice exhausted {route_id}: "
            + last.get("message", "no provider attempt was recorded"),
            failure_class=last.get("failure_class", "capability_transient"),
            code=last.get("failure_code", "provider_capability_unavailable"),
        )

    @staticmethod
    def _validate_semantics(value: dict[str, Any], allowed_actions: list[str]) -> None:
        action = value["action"]
        kind = action["kind"]
        if kind not in allowed_actions:
            raise ProviderFailure(
                "research decision selected an action outside the authoritative state boundary",
                "repairable_output", "structured_response_invalid",
            )
        advice_question = action["advice_question"]
        if kind == "ask_for_advice":
            if advice_question is None:
                raise ProviderFailure(
                    "ask_for_advice omitted its exact question",
                    "repairable_output", "structured_response_invalid",
                )
        elif advice_question is not None:
            raise ProviderFailure(
                f"{kind} supplied an advice-only question",
                "repairable_output", "structured_response_invalid",
            )
        acquisition = action["dataset_acquisition"]
        if kind == "acquire_dataset":
            if acquisition is None:
                raise ProviderFailure(
                    "acquire_dataset omitted its immutable source and adapter contract",
                    "repairable_output", "structured_response_invalid",
                )
            archive = acquisition["archive_format"]
            modality = acquisition["modality"]
            objective = acquisition["objective"]
            structured = acquisition["dataset_format"] != "text"
            invalid_adapter = any((
                (archive in {"zip", "tar"}) != (acquisition["records_member"] is not None),
                acquisition["dataset_format"] == "parquet" and archive != "none",
                modality == "image_text" and archive not in {"zip", "tar"},
                modality == "image_text" and (
                    acquisition["image_field"] is None or acquisition["caption_field"] is None
                ),
                modality == "text" and (
                    acquisition["image_field"] is not None or acquisition["caption_field"] is not None
                ),
                modality == "text" and objective == "prompt_completion" and (
                    acquisition["prompt_field"] is None
                    or acquisition["completion_field"] is None
                ),
                modality == "text" and structured and objective != "prompt_completion"
                and acquisition["text_field"] is None,
            ))
            if invalid_adapter:
                raise ProviderFailure(
                    "acquire_dataset supplied an inconsistent format, archive, modality, or field adapter",
                    "repairable_output", "structured_response_invalid",
                )
        elif acquisition is not None:
            raise ProviderFailure(
                f"{kind} supplied dataset-acquisition-only fields",
                "repairable_output", "structured_response_invalid",
            )
        launch_fields = (
            "experiment_title", "hypothesis", "dataset_id", "epochs",
            "order_policy", "order_seed", "intervention_type", "controls",
        )
        optional_launch_fields = (
            "control_experiment_id", "max_sessions", "max_events_per_session",
            "max_records_per_epoch",
        )
        if kind == "launch_experiment":
            if any(action[name] is None for name in launch_fields):
                raise ProviderFailure(
                    "launch_experiment omitted a required bounded experiment field",
                    "repairable_output", "structured_response_invalid",
                )
            if action["dataset_id"] == "builtin:foundation-visual-3022-v1":
                if (
                    action["max_sessions"] is None
                    or action["max_events_per_session"] is None
                    or action["max_records_per_epoch"] is not None
                    or action["epochs"] != 1
                    or action["order_policy"] != "declared"
                ):
                    raise ProviderFailure(
                        "the frozen bootstrap requires one declared-order epoch and session/event bounds",
                        "repairable_output", "structured_response_invalid",
                    )
                if action["max_events_per_session"] % 10:
                    raise ProviderFailure(
                        "bootstrap event bound must preserve complete ten-image concept blocks",
                        "repairable_output", "structured_response_invalid",
                    )
            elif (
                not action["dataset_id"].startswith("art-")
                or action["max_records_per_epoch"] is None
                or action["max_sessions"] is not None
                or action["max_events_per_session"] is not None
            ):
                raise ProviderFailure(
                    "registered datasets require an artifact id and record exposure instead of bootstrap session bounds",
                    "repairable_output", "structured_response_invalid",
                )
            if (
                action["intervention_type"] != "baseline"
                and action["control_experiment_id"] is None
            ):
                raise ProviderFailure(
                    "a non-baseline intervention must name its exact control experiment",
                    "repairable_output", "structured_response_invalid",
                )
            if action["controls"]["max_fanout"] > action["controls"]["max_degree"]:
                raise ProviderFailure(
                    "experiment max_fanout cannot exceed max_degree",
                    "repairable_output", "structured_response_invalid",
                )
        elif any(action[name] is not None for name in (*launch_fields, *optional_launch_fields)):
            raise ProviderFailure(
                f"{kind} supplied launch-only experiment fields",
                "repairable_output", "structured_response_invalid",
            )
        code_fields = (
            "code_change_title", "code_change_hypothesis", "code_change_objective",
            "code_change_acceptance_criteria", "code_change_scopes",
        )
        if kind == "modify_code":
            if any(action[name] is None for name in code_fields):
                raise ProviderFailure(
                    "modify_code omitted a required bounded code-change field",
                    "repairable_output", "structured_response_invalid",
                )
            if len(set(action["code_change_scopes"])) != len(action["code_change_scopes"]):
                raise ProviderFailure(
                    "modify_code repeated a source scope",
                    "repairable_output", "structured_response_invalid",
                )
        elif any(action[name] is not None for name in code_fields):
            raise ProviderFailure(
                f"{kind} supplied code-change-only fields",
                "repairable_output", "structured_response_invalid",
            )
        conclusion_fields = (
            "campaign_report", "next_campaign_title", "next_campaign_goal",
        )
        if kind == "conclude_campaign":
            if any(action[name] is None for name in conclusion_fields):
                raise ProviderFailure(
                    "campaign conclusion omitted its report or successor goal",
                    "repairable_output", "structured_response_invalid",
                )
        elif any(action[name] is not None for name in conclusion_fields):
            raise ProviderFailure(
                f"{kind} supplied conclusion-only fields",
                "repairable_output", "structured_response_invalid",
            )
