from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from training.executor.run_bakeoff import (
    CONFIG_PATH,
    read_json,
    run_task,
    start_server,
    stop_server,
)


PRIMARY_EXECUTOR = "gemma-4-26b-a4b"
LONG_CONTEXT_EXECUTOR = "ternary-bonsai-27b"
ALLOWED_EXECUTORS = {
    PRIMARY_EXECUTOR,
    LONG_CONTEXT_EXECUTOR,
    "qwen3.6-35b-a3b",
}
ALLOWED_ACTIONS = {
    "VALIDATE_JSON",
    "RUN_TESTS",
    "RETURN_VALIDATION_ERRORS",
    "NONE",
}


class ExecutorAdapterError(RuntimeError):
    pass


class ExecutorAdapter:
    """One bounded local-model job with at most one deterministic repair turn."""

    def __init__(
        self,
        *,
        repo_root: Path,
        config_path: Path = CONFIG_PATH,
        server_starter: Callable[..., tuple[Any, int]] = start_server,
        server_stopper: Callable[[Any], None] = stop_server,
        task_runner: Callable[..., dict[str, Any]] = run_task,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.config_path = config_path
        self.config = read_json(config_path)
        self.server_starter = server_starter
        self.server_stopper = server_stopper
        self.task_runner = task_runner

    def execute(
        self,
        *,
        execution_id: str,
        task: dict[str, Any],
        model_id: str | None = None,
        required_context_tokens: int = 0,
        max_model_attempts: int = 2,
    ) -> dict[str, Any]:
        self.validate_task(task)
        selected = self.select_model(model_id, required_context_tokens)
        if max_model_attempts not in {1, 2}:
            raise ExecutorAdapterError("max_model_attempts must be 1 or 2")
        model = copy.deepcopy(self.config["models"][selected])
        if required_context_tokens > int(model["context"]):
            raise ExecutorAdapterError(
                f"{selected} context {model['context']} is below required "
                f"{required_context_tokens}"
            )
        log_root = (
            Path(self.config["executor_root"]) / "logs" / "executor-jobs" / execution_id
        )
        log_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        process = None
        results: list[dict[str, Any]] = []
        try:
            process, port = self.server_starter(
                selected,
                model,
                self.config,
                log_root / "server.log",
            )
            first = self.task_runner(selected, port, task, attempt=1)
            results.append(first)
            if not first["valid"] and max_model_attempts == 2:
                results.append(
                    self.task_runner(
                        selected,
                        port,
                        task,
                        attempt=2,
                        prior_result=first,
                    )
                )
        finally:
            if process is not None:
                self.server_stopper(process)
        final = results[-1]
        return {
            "schema_version": "ninereeds_executor_job_result_v1",
            "execution_id": execution_id,
            "job_id": task["job_id"],
            "model_id": selected,
            "valid": bool(final["valid"]),
            "attempt_count": len(results),
            "attempts": [self._bounded_result(result) for result in results],
            "proposal": final.get("proposal"),
            "validation_errors": final.get("validation_errors") or [],
            "artifact_hashes": self._proposal_artifact_hashes(final.get("proposal")),
            "server_log": str(log_root / "server.log"),
        }

    def select_model(
        self,
        requested: str | None,
        required_context_tokens: int,
    ) -> str:
        if (
            isinstance(required_context_tokens, bool)
            or not isinstance(required_context_tokens, int)
            or required_context_tokens < 0
        ):
            raise ExecutorAdapterError("required_context_tokens must be a non-negative integer")
        selected = requested or (
            LONG_CONTEXT_EXECUTOR
            if required_context_tokens > 32768
            else PRIMARY_EXECUTOR
        )
        if selected not in ALLOWED_EXECUTORS or selected not in self.config["models"]:
            raise ExecutorAdapterError(f"executor model is not configured: {selected}")
        if selected != LONG_CONTEXT_EXECUTOR and required_context_tokens > 32768:
            raise ExecutorAdapterError(
                "jobs above 32K must use the commissioned long-context executor"
            )
        return selected

    def validate_task(self, task: Any) -> None:
        if not isinstance(task, dict):
            raise ExecutorAdapterError("executor task must be an object")
        required = {
            "job_id",
            "title",
            "instructions",
            "allowed_artifact_paths",
            "allowed_actions",
            "max_tokens",
        }
        if not required <= set(task):
            raise ExecutorAdapterError(
                f"executor task is missing fields: {sorted(required - set(task))}"
            )
        for field in ("job_id", "title", "instructions"):
            if not isinstance(task[field], str) or not task[field].strip():
                raise ExecutorAdapterError(f"executor task {field} must be non-empty")
        max_tokens = task["max_tokens"]
        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 16384
        ):
            raise ExecutorAdapterError("executor task max_tokens is outside 1..16384")
        actions = task["allowed_actions"]
        if not isinstance(actions, list) or not set(actions) <= ALLOWED_ACTIONS:
            raise ExecutorAdapterError("executor task contains an unsupported action")
        artifact_paths = task["allowed_artifact_paths"]
        if not isinstance(artifact_paths, list) or not all(
            isinstance(path, str) for path in artifact_paths
        ):
            raise ExecutorAdapterError("allowed_artifact_paths must be an array of strings")
        for relative in artifact_paths:
            self._safe_pipeline_path(relative, must_exist=False)
        for relative in task.get("context_files", []):
            self._safe_pipeline_path(relative, must_exist=True)
        for relative in task.get("artifact_json_schemas", {}).values():
            self._safe_pipeline_path(relative, must_exist=True)

    def _safe_pipeline_path(self, relative: str, *, must_exist: bool) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ExecutorAdapterError("pipeline path must be a non-empty string")
        path = (self.repo_root / relative).resolve()
        allowed = (self.repo_root / "training").resolve()
        if allowed not in path.parents:
            raise ExecutorAdapterError(f"executor path escapes the training root: {relative}")
        if must_exist and not path.is_file():
            raise ExecutorAdapterError(f"executor context file is missing: {relative}")
        return path

    @staticmethod
    def _bounded_result(result: dict[str, Any]) -> dict[str, Any]:
        return {
            key: result.get(key)
            for key in (
                "attempt",
                "valid",
                "validation_errors",
                "elapsed_seconds",
                "peak_gpu_memory_mib",
                "usage",
                "timings",
            )
        }

    @staticmethod
    def _proposal_artifact_hashes(
        proposal: dict[str, Any] | None,
    ) -> dict[str, str]:
        if not isinstance(proposal, dict):
            return {}
        result: dict[str, str] = {}
        for artifact in proposal.get("artifacts") or []:
            if not isinstance(artifact, dict):
                continue
            path = artifact.get("path")
            content = artifact.get("content")
            if isinstance(path, str) and isinstance(content, str):
                result[path] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return result
