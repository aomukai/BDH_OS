"""Zero-authority Luna enrichment for the deterministic research campaign journal."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..errors import RemoteJobError, SafetyError
from ..research_journal import ENRICHMENT_SCHEMA_VERSION
from ..schema import load_schema, validate
from .contracts import _declaration, _object_file
from .visual_provider import ProviderFailure, _codex


class ResearchJournalLibrarianHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        prompt = context.get("prompt")
        if not prompt:
            raise SafetyError("research journal librarian has no configured prompt")
        release_root = Path(context["release_root"]).resolve()
        schema_path = (release_root / prompt["output_schema"]).resolve()
        schema = load_schema(release_root, prompt["output_schema"])
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        prompt_text = (
            prompt["system"].strip()
            + "\n\nTask contract:\n"
            + prompt["template"].strip()
            + "\n\nAuthoritative experiment record:\n"
            + json.dumps(payload["record"], ensure_ascii=False, sort_keys=True)
        )
        attempts = []
        result = None
        selected = None
        for index, model in enumerate(context["route_models"]):
            provider = context["providers"][model["provider"]]
            attempt_root = run_root / f"attempt-{index + 1}"
            attempt_root.mkdir()
            try:
                value, transcript = _codex(
                    provider, model, prompt_text, schema_path, [], attempt_root,
                    reasoning_effort="low",
                )
                errors = validate(value, schema)
                if errors:
                    raise ProviderFailure(
                        "research journal enrichment failed schema validation: " + "; ".join(errors),
                        "repairable_output", "structured_response_invalid",
                    )
                result = value
                selected = model
                attempts.append({
                    "model_id": model["id"], "provider_id": provider["id"],
                    "status": "succeeded", "transcript": transcript,
                })
                break
            except ProviderFailure as exc:
                attempts.append({
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
                "research journal librarian exhausted its Luna route: "
                + last.get("message", "no provider attempt was recorded"),
                failure_class=last.get("failure_class", "capability_transient"),
                code=last.get("failure_code", "provider_capability_unavailable"),
            )

        enrichment = {
            "schema_version": ENRICHMENT_SCHEMA_VERSION,
            "campaign_id": payload["campaign_id"],
            "lab_id": payload["lab_id"],
            "experiment_id": payload["experiment_id"],
            "record_sha256": payload["record_sha256"],
            "model_id": selected["id"],
            "keywords": result["keywords"],
            "summary": result["summary"],
        }
        path, sha256, byte_size = _object_file(
            context["state_root"],
            (json.dumps(enrichment, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        transcript_document = {
            "schema_version": "ninereeds_research_journal_provider_transcript_v1",
            "experiment_id": payload["experiment_id"],
            "record_sha256": payload["record_sha256"],
            "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "attempts": attempts,
        }
        transcript_path, transcript_sha, transcript_size = _object_file(
            context["state_root"],
            (json.dumps(transcript_document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        manifest = {
            "schema_version": ENRICHMENT_SCHEMA_VERSION,
            "campaign_id": payload["campaign_id"],
            "lab_id": payload["lab_id"],
            "experiment_id": payload["experiment_id"],
            "record_sha256": payload["record_sha256"],
            "model_id": selected["id"],
            "authority": "none",
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _declaration(
                    "research_journal_enrichment", path, sha256, byte_size, manifest,
                ),
                _declaration(
                    "provider_transcript", transcript_path, transcript_sha, transcript_size,
                    {
                        "schema_version": "ninereeds_research_journal_provider_transcript_v1",
                        **manifest,
                    },
                ),
            ],
            "metrics": {
                "experiment_id": payload["experiment_id"],
                "record_sha256": payload["record_sha256"],
                "keyword_count": len(result["keywords"]),
                "authority": "none",
            },
            "failure": None,
        }
