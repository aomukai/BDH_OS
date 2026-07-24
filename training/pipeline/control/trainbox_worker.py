from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from .executor_adapter import ExecutorAdapter
from .grade_finalize import GradeFinalizeError, finalize_grade
from .ledger import ControlLedger, LedgerError
from .msm_trainer import MsmTrainer
from training.pipeline.cortex.script_examples import (
    CortexScriptError,
    validate_msm_script,
)


DEFAULT_REPO = Path("/home/aomukai/Ninereeds")
DEFAULT_CONTROL_ROOT = Path("/home/aomukai/.local/state/ninereeds-control")
UNSLOTH_PYTHON = Path("/home/aomukai/.unsloth/studio/unsloth_studio/bin/python")
CORTEX_PYTHON = Path("/home/aomukai/.venvs/ninereeds-cortex/bin/python")
SUPPORTED_PHASES = {"phase_0_form", "phase_1_word_form"}
VALUE_OPTIONS = {
    "--parent",
    "--examples",
    "--epochs",
    "--lr",
    "--batch-size",
    "--block-size",
    "--prompt-tail-bytes",
    "--seed",
    "--device",
    "--probe-max-new-tokens",
    "--probe-temperature",
    "--probe-top-k",
}
FLAG_OPTIONS = {
    "--amp-bf16",
    "--adam8bit",
    "--no-shuffle",
    "--skip-probes",
    "--dry-run",
}
CORTEX_VALUE_OPTIONS = {
    "--parent",
    "--epochs",
    "--batch-size",
    "--max-examples",
    "--lr",
    "--weight-decay",
    "--seed",
    "--ingress-device",
    "--core-device",
    "--rms-clip",
    "--probe-max-new-tokens",
}
CORTEX_FLAG_OPTIONS = {"--stochastic-rounding", "--local-files-only"}


class PlanBlocked(RuntimeError):
    pass


class PlanResultBlocked(PlanBlocked):
    def __init__(self, message: str, result: dict[str, Any]) -> None:
        super().__init__(message)
        self.result = result


class TrainboxWorker:
    def __init__(
        self,
        ledger: ControlLedger,
        *,
        repo_root: Path = DEFAULT_REPO,
        worker_id: str | None = None,
        lease_seconds: int = 1200,
        allow_live: bool = False,
        command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]]
        | None = None,
        executor_adapter: ExecutorAdapter | None = None,
        msm_trainer: MsmTrainer | None = None,
    ) -> None:
        self.ledger = ledger
        self.repo_root = repo_root.resolve()
        self.worker_id = worker_id or f"trainbox:{socket.gethostname()}:{os.getpid()}"
        self.lease_seconds = lease_seconds
        self.allow_live = allow_live
        self.command_runner = command_runner
        self.executor_adapter = executor_adapter
        self.msm_trainer = msm_trainer
        self.worker_lock = self.ledger.worker_dir / "trainbox-worker.lock"

    def drain(self, *, max_plans: int | None = None) -> dict[str, int | bool]:
        self.worker_lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.worker_lock.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {
                    "acquired": False,
                    "processed": 0,
                    "completed": 0,
                    "blocked": 0,
                    "failed": 0,
                }
            return self._drain_locked(max_plans=max_plans)

    def _drain_locked(self, *, max_plans: int | None) -> dict[str, int | bool]:
        processed = completed = blocked = failed = 0
        for plan in self.ledger.pending_plans():
            if max_plans is not None and processed >= max_plans:
                break
            claim = self.ledger.claim(
                plan["plan_id"],
                self.worker_id,
                self.lease_seconds,
            )
            if claim is None:
                continue
            processed += 1
            try:
                self.ledger.mark_running(plan["plan_id"], self.worker_id)
                result, artifact_hashes = self.execute(plan)
                self.ledger.complete(
                    plan["plan_id"],
                    self.worker_id,
                    status="succeeded",
                    result=result,
                    artifact_hashes=artifact_hashes,
                )
                completed += 1
            except PlanResultBlocked as exc:
                result = dict(exc.result)
                result.setdefault("error", str(exc))
                result.setdefault("error_type", "plan_result_blocked")
                self.ledger.complete(
                    plan["plan_id"],
                    self.worker_id,
                    status="blocked",
                    result=result,
                    artifact_hashes=result.get("artifact_hashes"),
                )
                blocked += 1
            except PlanBlocked as exc:
                self.ledger.complete(
                    plan["plan_id"],
                    self.worker_id,
                    status="blocked",
                    result={"error": str(exc), "error_type": "plan_blocked"},
                )
                blocked += 1
            except Exception as exc:
                self.ledger.fail_retryable(
                    plan["plan_id"],
                    self.worker_id,
                    f"{type(exc).__name__}: {exc}",
                )
                failed += 1
        return {
            "acquired": True,
            "processed": processed,
            "completed": completed,
            "blocked": blocked,
            "failed": failed,
        }

    def execute(
        self, plan: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        kind = plan["kind"]
        if kind == "phase_block":
            return self._execute_phase_block(plan)
        if kind == "cortex_block":
            return self._execute_cortex_block(plan)
        if kind == "executor_job":
            return self._execute_executor_job(plan)
        if kind == "trainer_session":
            return self._execute_trainer_session(plan)
        raise PlanBlocked(f"plan kind is not commissioned on the trainbox: {kind}")

    def _execute_cortex_block(
        self, plan: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        payload = plan["payload"]
        common = {"output_checkpoint", "runner_args"}
        if frozenset(payload) not in {
            frozenset(common | {"jsonl_path"}),
            frozenset(common | {"script"}),
        }:
            raise PlanBlocked("cortex_block payload fields do not match v1")
        runner_args = payload["runner_args"]
        if not isinstance(runner_args, list) or not all(
            isinstance(value, str) for value in runner_args
        ):
            raise PlanBlocked("cortex runner_args must be an array of strings")
        self._validate_option_list(
            runner_args,
            value_options=CORTEX_VALUE_OPTIONS,
            flag_options=CORTEX_FLAG_OPTIONS,
        )
        jsonl_path = None
        script = payload.get("script")
        if script is None:
            jsonl_path = self._safe_cortex_path(
                payload["jsonl_path"],
                root="training/pipeline/cortex",
                suffix=".jsonl",
                must_exist=True,
            )
        else:
            try:
                validate_msm_script(
                    script,
                    self.repo_root / "training/pipeline/script_schema.json",
                )
            except (CortexScriptError, OSError) as exc:
                raise PlanBlocked(str(exc)) from exc
        output = self._safe_cortex_path(
            payload["output_checkpoint"],
            root="core/cortex",
            suffix=".pt",
            must_exist=False,
        )
        parent_value = self._option_value(runner_args, "--parent")
        if parent_value is not None and parent_value != "scratch":
            self._safe_cortex_path(
                parent_value,
                root="core/cortex",
                suffix=".pt",
                must_exist=True,
            )
        if plan["mode"] == "shadow":
            if any(plan["authorization"].values()):
                raise PlanBlocked("shadow Cortex plan unexpectedly authorizes mutation")
            return (
                {
                    "kind": "cortex_block",
                    "mode": "shadow",
                    "status": "planned",
                    "training_source": (
                        {
                            "type": "msm_script",
                            "script_id": script["script_id"],
                            "session_id": script["session_id"],
                        }
                        if script is not None
                        else {
                            "type": "jsonl",
                            "path": jsonl_path.relative_to(
                                self.repo_root
                            ).as_posix(),
                        }
                    ),
                    "checkpoint_after": output.relative_to(self.repo_root).as_posix(),
                },
                {},
            )
        if not self.allow_live:
            raise PlanBlocked("live Cortex execution is disabled by the trainbox machine gate")
        if not plan["authorization"]["allow_weight_updates"]:
            raise PlanBlocked("live Cortex block lacks weight-update authorization")
        if plan["authorization"]["allow_checkpoint_promotion"]:
            raise PlanBlocked("Cortex block cannot promote its own checkpoint")
        if not CORTEX_PYTHON.is_file():
            raise PlanBlocked("the commissioned Cortex Python environment is missing")
        if output.exists():
            raise PlanBlocked(
                f"Cortex output checkpoint already exists: {payload['output_checkpoint']}"
            )
        command = [
            str(CORTEX_PYTHON),
            "meta/scripts/cortex_runtime.py",
            "meta/scripts/train_cortex.py",
            *(
                ["--script-stdin"]
                if script is not None
                else [
                    "--jsonl",
                    jsonl_path.relative_to(self.repo_root).as_posix(),
                ]
            ),
            "--output",
            output.relative_to(self.repo_root).as_posix(),
            *runner_args,
        ]
        completed = self._run_with_lease(
            command,
            plan["plan_id"],
            input_text=(
                json.dumps(script, ensure_ascii=False)
                if script is not None
                else None
            ),
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"Cortex trainer exited {completed.returncode}: {detail[-3000:]}"
            )
        try:
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Cortex trainer returned invalid JSON") from exc
        if not output.is_file():
            raise RuntimeError("Cortex trainer did not write its checkpoint")
        relative = output.relative_to(self.repo_root).as_posix()
        return (
            {
                "kind": "cortex_block",
                "mode": "live",
                "status": "completed",
                "checkpoint_after": relative,
                "metadata": result.get("metadata"),
            },
            {relative: self._file_sha256(output)},
        )

    def _execute_executor_job(
        self, plan: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        payload = plan["payload"]
        workflow = payload.get("workflow")
        expected = {
            "task",
            "model_id",
            "required_context_tokens",
            "max_model_attempts",
        }
        if frozenset(payload) not in {
            frozenset(expected),
            frozenset(expected | {"workflow"}),
        }:
            raise PlanBlocked("executor_job payload fields do not match the v1 contract")
        if "workflow" in payload and not isinstance(payload["workflow"], dict):
            raise PlanBlocked("executor_job workflow metadata must be an object")
        if plan["authorization"]["allow_weight_updates"] and (
            not isinstance(workflow, dict)
            or workflow.get("type") != "cortex_train"
        ):
            raise PlanBlocked(
                "executor proposal job can carry weight authority only for a "
                "separate Cortex training child"
            )
        if plan["authorization"]["allow_checkpoint_promotion"]:
            raise PlanBlocked("executor proposal job cannot authorize checkpoint promotion")
        adapter = self.executor_adapter or ExecutorAdapter(repo_root=self.repo_root)
        result = adapter.execute(
            execution_id=plan["plan_id"],
            task=payload["task"],
            model_id=payload["model_id"],
            required_context_tokens=payload["required_context_tokens"],
            max_model_attempts=payload["max_model_attempts"],
        )
        artifact_hashes = result.pop("artifact_hashes")
        if not result["valid"]:
            result["artifact_hashes"] = artifact_hashes
            raise PlanResultBlocked(
                "executor could not produce a valid proposal within its attempt budget",
                result,
            )
        if isinstance(workflow, dict) and workflow.get("type") == "msm_grade":
            try:
                grade, grade_hashes = self._finalize_grade_workflow(
                    result,
                    workflow,
                )
            except GradeFinalizeError as exc:
                result["artifact_hashes"] = artifact_hashes
                raise PlanResultBlocked(
                    f"executor grade failed deterministic finalization: {exc}",
                    result,
                ) from exc
            result["grade"] = grade
            artifact_hashes.update(grade_hashes)
        return result, artifact_hashes

    def _finalize_grade_workflow(
        self,
        result: dict[str, Any],
        workflow: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        expected = {
            "type",
            "session_id",
            "script_path",
            "raw_log_path",
            "artifact_path",
            "continuation",
        }
        if set(workflow) != expected:
            raise GradeFinalizeError("msm_grade workflow fields do not match v1")
        proposal = result.get("proposal")
        artifacts = {
            artifact.get("path"): artifact.get("content")
            for artifact in (proposal or {}).get("artifacts") or []
            if isinstance(artifact, dict)
        }
        content = artifacts.get(workflow["artifact_path"])
        if not isinstance(content, str):
            raise GradeFinalizeError("executor proposal lacks the grade artifact")
        try:
            proposed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise GradeFinalizeError("executor grade artifact is invalid JSON") from exc
        if proposed.get("session_id") != workflow["session_id"]:
            raise GradeFinalizeError("executor grade session differs from workflow")
        return finalize_grade(
            proposed,
            repo_root=self.repo_root,
            script_path=workflow["script_path"],
            raw_log_path=workflow["raw_log_path"],
            artifact_path=workflow["artifact_path"],
        )

    def _execute_trainer_session(
        self, plan: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        payload = plan["payload"]
        expected = {"script", "checkpoint_path", "inference"}
        if frozenset(payload) not in {
            frozenset(expected),
            frozenset(expected | {"continuation"}),
            frozenset(expected | {"continuation", "shadow_transcript"}),
        }:
            raise PlanBlocked("trainer_session payload fields do not match the v1 contract")
        if plan["authorization"]["allow_weight_updates"]:
            raise PlanBlocked("trainer session cannot authorize weight updates")
        if plan["authorization"]["allow_checkpoint_promotion"]:
            raise PlanBlocked("trainer session cannot authorize checkpoint promotion")
        if plan["mode"] == "live" and not self.allow_live:
            raise PlanBlocked("live trainer execution is disabled by the trainbox machine gate")
        trainer = self.msm_trainer or MsmTrainer(repo_root=self.repo_root)
        if self.msm_trainer is not None or plan["mode"] == "shadow":
            return trainer.run(
                script=payload["script"],
                mode=plan["mode"],
                checkpoint_path=payload["checkpoint_path"],
                inference=payload["inference"],
                shadow_transcript=payload.get("shadow_transcript"),
            )
        if not UNSLOTH_PYTHON.is_file():
            raise PlanBlocked("the commissioned trainer Python environment is missing")
        request = {
            "script": payload["script"],
            "mode": plan["mode"],
            "checkpoint_path": payload["checkpoint_path"],
            "inference": payload["inference"],
            "shadow_transcript": payload.get("shadow_transcript"),
        }
        completed = self._run_with_lease(
            [
                str(UNSLOTH_PYTHON),
                "-m",
                "training.pipeline.control.trainer_cli",
                "--repo",
                str(self.repo_root),
            ],
            plan["plan_id"],
            input_text=json.dumps(request, ensure_ascii=False),
            environment={**os.environ, "CUDA_VISIBLE_DEVICES": "1"},
        )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("trainer subprocess returned invalid JSON") from exc
        if completed.returncode != 0 or not response.get("ok"):
            raise RuntimeError(response.get("error") or completed.stderr[-3000:])
        return response["result"], response["artifact_hashes"]

    def _execute_phase_block(
        self, plan: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        payload = plan["payload"]
        if set(payload) - {"phase_id", "runner_args", "continuation"}:
            raise PlanBlocked("phase_block payload contains undeclared fields")
        continuation = payload.get("continuation")
        if continuation is not None:
            if (
                not isinstance(continuation, dict)
                or set(continuation) != {"remaining_blocks"}
                or isinstance(continuation["remaining_blocks"], bool)
                or not isinstance(continuation["remaining_blocks"], int)
                or not 0 <= continuation["remaining_blocks"] <= 10
            ):
                raise PlanBlocked("phase continuation must contain remaining_blocks 0..10")
        phase_id = payload.get("phase_id")
        if phase_id not in SUPPORTED_PHASES:
            raise PlanBlocked(f"phase is not implemented by the bounded runner: {phase_id}")
        runner_args = payload.get("runner_args", [])
        if not isinstance(runner_args, list) or not all(
            isinstance(value, str) for value in runner_args
        ):
            raise PlanBlocked("runner_args must be an array of strings")
        self._validate_runner_args(runner_args)

        if plan["mode"] == "shadow":
            if any(plan["authorization"].values()):
                raise PlanBlocked("shadow plan unexpectedly authorizes mutation")
            runner_args = [value for value in runner_args if value != "--dry-run"]
            runner_args.append("--dry-run")
        else:
            if not self.allow_live:
                raise PlanBlocked("live execution is disabled by the trainbox machine gate")
            if not plan["authorization"]["allow_weight_updates"]:
                raise PlanBlocked("live phase block lacks weight-update authorization")
            if "--dry-run" in runner_args:
                raise PlanBlocked("live phase block must not include --dry-run")

        runner_python = (
            UNSLOTH_PYTHON if plan["mode"] == "live" else Path("/usr/bin/python3")
        )
        if not runner_python.is_file():
            raise PlanBlocked(
                f"phase runner Python environment is missing: {runner_python}"
            )
        command = [
            str(runner_python),
            "meta/scripts/msm_phase_runner.py",
            "--phase-id",
            phase_id,
            *runner_args,
        ]
        completed = self._run_with_lease(command, plan["plan_id"])
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"phase runner exited {completed.returncode}: {detail[-3000:]}"
            )
        try:
            output = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("phase runner returned invalid JSON") from exc
        report_path = self._safe_repo_path(output.get("block_report"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_status = "planned" if plan["mode"] == "shadow" else None
        if expected_status and report.get("status") != expected_status:
            raise RuntimeError("shadow phase runner did not produce a planned report")
        artifact_hashes = self._artifact_hashes(report)
        return (
            {
                "kind": "phase_block",
                "mode": plan["mode"],
                "phase_id": phase_id,
                "block_id": report.get("block_id"),
                "block_status": report.get("status"),
                "gate_status": report.get("gate_status"),
                "local_recommendation": report.get("local_recommendation"),
                "checkpoint_after": report.get("checkpoint_after"),
                "metrics": report.get("metrics"),
                "block_report": report_path.relative_to(self.repo_root).as_posix(),
                "runner_stdout": output,
            },
            artifact_hashes,
        )

    def _run_with_lease(
        self,
        command: list[str],
        plan_id: str,
        *,
        input_text: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if self.command_runner is not None:
            return self.command_runner(command)
        with (
            tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stdout_file,
            tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr_file,
        ):
            process = subprocess.Popen(
                command,
                cwd=self.repo_root,
                text=True,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=stdout_file,
                stderr=stderr_file,
                env=environment,
            )
            if process.stdin is not None:
                process.stdin.write(input_text or "")
                process.stdin.close()
            renewal_interval = max(5, min(60, self.lease_seconds // 3))
            next_renewal = time.monotonic() + renewal_interval
            while process.poll() is None:
                time.sleep(1)
                if time.monotonic() >= next_renewal:
                    self.ledger.renew_claim(
                        plan_id,
                        self.worker_id,
                        self.lease_seconds,
                    )
                    next_renewal = time.monotonic() + renewal_interval
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read()
            stderr = stderr_file.read()
        return subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    @staticmethod
    def _validate_runner_args(values: list[str]) -> None:
        TrainboxWorker._validate_option_list(
            values,
            value_options=VALUE_OPTIONS,
            flag_options=FLAG_OPTIONS,
        )

    @staticmethod
    def _validate_option_list(
        values: list[str],
        *,
        value_options: set[str],
        flag_options: set[str],
    ) -> None:
        index = 0
        while index < len(values):
            option = values[index]
            if option in flag_options:
                index += 1
                continue
            if option in value_options:
                if index + 1 >= len(values) or values[index + 1].startswith("--"):
                    raise PlanBlocked(f"runner option requires a value: {option}")
                index += 2
                continue
            raise PlanBlocked(f"runner option is not allowed: {option}")

    def _safe_cortex_path(
        self,
        value: Any,
        *,
        root: str,
        suffix: str,
        must_exist: bool,
    ) -> Path:
        if not isinstance(value, str) or not value:
            raise PlanBlocked("Cortex path must be a non-empty string")
        path = (self.repo_root / value).resolve()
        allowed = (self.repo_root / root).resolve()
        if allowed not in path.parents or path.suffix != suffix:
            raise PlanBlocked(f"Cortex path is outside {root}: {value}")
        if must_exist and not path.is_file():
            raise PlanBlocked(f"Cortex input is missing: {value}")
        return path

    @staticmethod
    def _option_value(values: list[str], option: str) -> str | None:
        found: str | None = None
        for index, value in enumerate(values):
            if value == option:
                if found is not None:
                    raise PlanBlocked(f"runner option is duplicated: {option}")
                found = values[index + 1]
        return found

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _safe_repo_path(self, value: Any) -> Path:
        if not isinstance(value, str) or not value:
            raise RuntimeError("runner did not identify its block report")
        path = (self.repo_root / value).resolve()
        if self.repo_root not in path.parents:
            raise RuntimeError("runner artifact escaped the repository")
        expected_root = (self.repo_root / "training/pipeline/msm/phase_blocks").resolve()
        if expected_root not in path.parents or path.name != "block_report.json":
            raise RuntimeError("runner reported an unexpected artifact path")
        if not path.is_file():
            raise RuntimeError("runner block report is missing")
        return path

    def _artifact_hashes(self, report: dict[str, Any]) -> dict[str, str]:
        artifacts = report.get("artifacts")
        if not isinstance(artifacts, dict):
            raise RuntimeError("block report has no artifact manifest")
        hashes: dict[str, str] = {}
        for value in artifacts.values():
            if value is None:
                continue
            path = self._safe_artifact_path(value)
            hashes[path.relative_to(self.repo_root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        return hashes

    def _safe_artifact_path(self, value: Any) -> Path:
        if not isinstance(value, str) or not value:
            raise RuntimeError("artifact path must be a non-empty string")
        path = (self.repo_root / value).resolve()
        allowed = (self.repo_root / "training/pipeline/msm/phase_blocks").resolve()
        if allowed not in path.parents or not path.is_file():
            raise RuntimeError(f"artifact is missing or outside the phase block root: {value}")
        return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Drain bounded trainbox control plans.")
    parser.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL_ROOT)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--max-plans", type=int)
    parser.add_argument("--lease-seconds", type=int, default=1200)
    args = parser.parse_args()
    worker = TrainboxWorker(
        ControlLedger(args.control_root),
        repo_root=args.repo,
        lease_seconds=args.lease_seconds,
        allow_live=os.environ.get("NINEREEDS_ALLOW_LIVE", "0") == "1",
    )
    result = worker.drain(max_plans=args.max_plans)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
