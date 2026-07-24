from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class TrainerError(RuntimeError):
    pass


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class MsmTrainer:
    """Execute fixed MSM scripts faithfully; never grade or choose the next item."""

    def __init__(
        self,
        *,
        repo_root: Path,
        inference_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.sessions_root = (
            self.repo_root / "training/pipeline/msm/sessions"
        ).resolve()
        self.script_schema = self.repo_root / "training/pipeline/script_schema.json"
        self.raw_schema = self.repo_root / "training/pipeline/raw_chat_line_schema.json"
        self.inference_factory = inference_factory

    def run(
        self,
        *,
        script: dict[str, Any],
        mode: str,
        checkpoint_path: str | None,
        inference: dict[str, Any],
        shadow_transcript: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        self._validate_json(script, self.script_schema)
        if mode not in {"shadow", "live"}:
            raise TrainerError("trainer mode must be shadow or live")
        session_id = script["session_id"]
        self._validate_identifier(session_id)
        session_dir = self.sessions_root / session_id
        if session_dir.exists():
            existing_script = session_dir / "script.json"
            existing_manifest = session_dir / "trainer_manifest.json"
            if existing_script.is_file() and existing_manifest.is_file():
                stored_script = json.loads(existing_script.read_text(encoding="utf-8"))
                manifest = json.loads(existing_manifest.read_text(encoding="utf-8"))
                if stored_script != script:
                    raise TrainerError(
                        f"session ID collision with a different script: {session_id}"
                    )
                if (
                    manifest.get("mode") == mode
                    and manifest.get("status") in {"planned", "simulated", "completed"}
                ):
                    paths = [existing_script, existing_manifest]
                    raw = session_dir / "raw_chat.jsonl"
                    if raw.is_file():
                        paths.insert(1, raw)
                    return self._result(manifest), self._hashes(*paths)
            raise TrainerError(
                f"session exists in a non-replayable state: {session_id}"
            )
        session_dir.mkdir(mode=0o700, parents=True)
        script_path = session_dir / "script.json"
        raw_path = session_dir / "raw_chat.jsonl"
        manifest_path = session_dir / "trainer_manifest.json"
        self._write_json_atomic(script_path, script)

        manifest: dict[str, Any] = {
            "schema_version": "msm_trainer_manifest_v1",
            "session_id": session_id,
            "script_id": script["script_id"],
            "mode": mode,
            "status": "planned" if mode == "shadow" else "running",
            "created_at": utc_now(),
            "completed_at": None,
            "checkpoint": checkpoint_path,
            "item_count": len(script["items"]),
            "event_count": 0,
            "artifacts": {
                "script": script_path.relative_to(self.repo_root).as_posix(),
                "raw_log": None,
                "manifest": manifest_path.relative_to(self.repo_root).as_posix(),
            },
            "error": None,
        }
        if mode == "shadow":
            if shadow_transcript is not None:
                sequence = self._write_shadow_transcript(
                    raw_path, script, shadow_transcript
                )
                manifest["status"] = "simulated"
                manifest["event_count"] = sequence
                manifest["artifacts"]["raw_log"] = raw_path.relative_to(
                    self.repo_root
                ).as_posix()
            manifest["completed_at"] = utc_now()
            self._write_json_atomic(manifest_path, manifest)
            paths = [script_path]
            if raw_path.is_file():
                paths.append(raw_path)
            paths.append(manifest_path)
            return self._result(manifest), self._hashes(*paths)
        if shadow_transcript is not None:
            raise TrainerError("shadow_transcript is forbidden in live mode")

        checkpoint = self._safe_checkpoint(checkpoint_path)
        model = self._model(checkpoint, inference)
        sequence = 0
        try:
            for item in script["items"]:
                prompt = item["user_prompt"]
                sequence = self._event(
                    raw_path,
                    script,
                    item,
                    sequence,
                    event_type="user_prompt",
                    speaker="user",
                    text=prompt,
                    checkpoint=checkpoint_path,
                )
                original_prompt = f"[user] {prompt}\n[Ninereeds]"
                started = time.monotonic()
                original = model.generate_text(original_prompt)
                latency = round((time.monotonic() - started) * 1000, 3)
                sequence = self._event(
                    raw_path,
                    script,
                    item,
                    sequence,
                    event_type="ninereeds_original_answer",
                    speaker="ninereeds",
                    text=original,
                    checkpoint=checkpoint_path,
                    latency_ms=latency,
                    inference=inference,
                )
                correction = item.get("teacher_correction")
                if correction is not None:
                    sequence = self._event(
                        raw_path,
                        script,
                        item,
                        sequence,
                        event_type="teacher_correction",
                        speaker="teacher",
                        text=correction,
                        checkpoint=checkpoint_path,
                    )
                if item["ask_after_correction"]:
                    if correction is None:
                        raise TrainerError(
                            f"{item['item_id']} asks after correction but has no correction"
                        )
                    replay_prompt = (
                        f"[user] {prompt}\n[Ninereeds] {original}\n"
                        f"[teacher] {correction}\n[Ninereeds]"
                    )
                    started = time.monotonic()
                    after = model.generate_text(replay_prompt)
                    latency = round((time.monotonic() - started) * 1000, 3)
                    sequence = self._event(
                        raw_path,
                        script,
                        item,
                        sequence,
                        event_type="ninereeds_after_correction_answer",
                        speaker="ninereeds",
                        text=after,
                        checkpoint=checkpoint_path,
                        latency_ms=latency,
                        inference=inference,
                    )
        except Exception as exc:
            manifest["status"] = "failed"
            manifest["completed_at"] = utc_now()
            manifest["event_count"] = sequence
            manifest["artifacts"]["raw_log"] = (
                raw_path.relative_to(self.repo_root).as_posix()
                if raw_path.exists()
                else None
            )
            manifest["error"] = {"type": type(exc).__name__, "message": str(exc)}
            self._write_json_atomic(manifest_path, manifest)
            raise

        manifest["status"] = "completed"
        manifest["completed_at"] = utc_now()
        manifest["event_count"] = sequence
        manifest["artifacts"]["raw_log"] = raw_path.relative_to(
            self.repo_root
        ).as_posix()
        self._write_json_atomic(manifest_path, manifest)
        return (
            self._result(manifest),
            self._hashes(script_path, raw_path, manifest_path),
        )

    def _write_shadow_transcript(
        self,
        path: Path,
        script: dict[str, Any],
        transcript: list[dict[str, Any]],
    ) -> int:
        if not isinstance(transcript, list) or len(transcript) != len(script["items"]):
            raise TrainerError("shadow transcript must contain one entry per script item")
        sequence = 0
        for item, response in zip(script["items"], transcript, strict=True):
            if not isinstance(response, dict) or set(response) != {
                "item_id",
                "original_answer",
                "after_correction_answer",
            }:
                raise TrainerError("shadow transcript entry fields do not match v1")
            if response["item_id"] != item["item_id"]:
                raise TrainerError("shadow transcript item order differs from the script")
            original = response["original_answer"]
            after = response["after_correction_answer"]
            if not isinstance(original, str) or (
                after is not None and not isinstance(after, str)
            ):
                raise TrainerError("shadow transcript answers must be strings or null")
            sequence = self._event(
                path,
                script,
                item,
                sequence,
                event_type="user_prompt",
                speaker="user",
                text=item["user_prompt"],
                checkpoint=None,
            )
            sequence = self._event(
                path,
                script,
                item,
                sequence,
                event_type="ninereeds_original_answer",
                speaker="ninereeds",
                text=original,
                checkpoint=None,
            )
            correction = item.get("teacher_correction")
            if correction is not None:
                sequence = self._event(
                    path,
                    script,
                    item,
                    sequence,
                    event_type="teacher_correction",
                    speaker="teacher",
                    text=correction,
                    checkpoint=None,
                )
            if item["ask_after_correction"]:
                if not isinstance(after, str):
                    raise TrainerError(
                        "shadow transcript lacks requested corrected answer"
                    )
                sequence = self._event(
                    path,
                    script,
                    item,
                    sequence,
                    event_type="ninereeds_after_correction_answer",
                    speaker="ninereeds",
                    text=after,
                    checkpoint=None,
                )
            elif after is not None:
                raise TrainerError(
                    "shadow transcript has an unrequested corrected answer"
                )
        return sequence

    def _model(self, checkpoint: Path, inference: dict[str, Any]) -> Any:
        allowed = {"max_new_tokens", "temperature", "top_k", "device"}
        if set(inference) != allowed:
            raise TrainerError("inference fields do not match the trainer contract")
        if self.inference_factory is None:
            from inference import BDHInference

            factory = BDHInference
        else:
            factory = self.inference_factory
        return factory(checkpoint_path=checkpoint, **inference)

    def _event(
        self,
        path: Path,
        script: dict[str, Any],
        item: dict[str, Any],
        sequence: int,
        *,
        event_type: str,
        speaker: str,
        text: str,
        checkpoint: str | None,
        latency_ms: float | None = None,
        inference: dict[str, Any] | None = None,
    ) -> int:
        event = {
            "schema_version": "msm_raw_chat_line_v1",
            "session_id": script["session_id"],
            "script_id": script["script_id"],
            "item_id": item["item_id"],
            "sequence_index": sequence,
            "event_type": event_type,
            "speaker": speaker,
            "text": text,
            "created_at": utc_now(),
            "latency_ms": latency_ms,
            "checkpoint": checkpoint,
            "inference": inference,
            "error": None,
        }
        self._validate_json(event, self.raw_schema)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return sequence + 1

    def _safe_checkpoint(self, value: str | None) -> Path:
        if not isinstance(value, str) or not value:
            raise TrainerError("live trainer session requires a checkpoint path")
        path = (self.repo_root / value).resolve()
        allowed_roots = [
            (self.repo_root / "core").resolve(),
            (self.repo_root / "checkpoints").resolve(),
        ]
        if not any(root in path.parents for root in allowed_roots) or not path.is_file():
            raise TrainerError("checkpoint is missing or outside an allowed root")
        return path

    @staticmethod
    def _validate_identifier(value: Any) -> None:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 160
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._"
                for character in value
            )
        ):
            raise TrainerError("invalid session_id")

    @staticmethod
    def _validate_json(value: dict[str, Any], schema_path: Path) -> None:
        try:
            import jsonschema
        except ImportError as exc:
            raise TrainerError("python jsonschema is required") from exc
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(value, schema)
        except jsonschema.ValidationError as exc:
            raise TrainerError(f"{schema_path.name}: {exc.message}") from exc

    def _result(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "msm_trainer_result_v1",
            "session_id": manifest["session_id"],
            "mode": manifest["mode"],
            "status": manifest["status"],
            "event_count": manifest["event_count"],
            "artifacts": manifest["artifacts"],
        }

    def _hashes(self, *paths: Path) -> dict[str, str]:
        return {
            path.relative_to(self.repo_root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in paths
        }

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
