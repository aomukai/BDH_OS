from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import subprocess
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lab.backend.config import LabConfig
from lab.backend.messages.store import MessageStore


STATUS_SCHEMA = "ninereeds_provider_status_v1"
RATE_LIMIT_PATTERNS = (
    "rate limit",
    "rate_limit",
    "usage limit",
    "quota exceeded",
    "too many requests",
    "http 429",
    "status 429",
)
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_STRATEGIC_MODEL = "deepseek/deepseek-v4-flash-0731"
DEEPSEEK_CHAT_COMPLETIONS_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_STRATEGIC_MODEL = "deepseek-v4-flash"
STRATEGIC_PROVIDER_OPTIONS = {"codex_fugu", "openrouter", "deepseek"}


class ProviderError(RuntimeError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class BothProvidersLimitedError(ProviderError):
    pass


def utc_now(timestamp: float | None = None) -> str:
    value = time.time() if timestamp is None else timestamp
    return (
        datetime.fromtimestamp(value, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
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


def _read_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _environment_with_dotenv(repo_root: Path, allowed_keys: set[str]) -> dict[str, str]:
    result = dict(os.environ)
    try:
        lines = (repo_root / ".env").read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in allowed_keys:
            result.setdefault(key, value.strip().strip("\"'"))
    return result


def _json_object_from_text(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        value = None
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                value = candidate
                break
        if value is None:
            raise
    if not isinstance(value, dict):
        raise ProviderUnavailableError("provider returned a non-object response")
    return value


def _safe_error(text: str, limit: int = 2000) -> str:
    # Provider stderr can contain request identifiers but must never be allowed to
    # spill arbitrary environment/configuration data into durable public status.
    clean = re.sub(r"(?i)(api[-_ ]?key|authorization|bearer)\s*[:=]\s*\S+", r"\1=<redacted>", text)
    return clean.strip()[-limit:]


def is_rate_limit_error(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS)


def _failure_summary(text: str) -> str:
    indicators = (
        "error",
        "failed",
        "rate limit",
        "rate_limit",
        "429",
        "timeout",
        "unauthorized",
        "forbidden",
    )
    lines = [
        line.strip()
        for line in text.splitlines()
        if any(indicator in line.lower() for indicator in indicators)
    ]
    return _safe_error("\n".join(lines[-12:]) or "provider invocation failed")


class CodexRateLimitReader:
    """Read ChatGPT/Codex limits through the installed app-server JSON-RPC API."""

    def __init__(
        self,
        executable: str = "/home/aomukai/.local/bin/codex",
        *,
        timeout_seconds: int = 10,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def read(self) -> dict[str, Any]:
        command = [self.executable, "app-server", "--stdio"]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        messages = (
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "ninereeds-provider-monitor",
                        "version": "1",
                    }
                },
            },
            {"method": "initialized", "params": {}},
            {"method": "account/rateLimits/read", "id": 2, "params": None},
        )
        try:
            for message in messages:
                process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            process.stdin.flush()
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            deadline = time.monotonic() + self.timeout_seconds
            errors: list[str] = []
            while time.monotonic() < deadline:
                for key, _ in selector.select(timeout=min(0.5, max(0.0, deadline - time.monotonic()))):
                    line = key.fileobj.readline()
                    if not line:
                        continue
                    if key.data == "stderr":
                        errors.append(line)
                        continue
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if message.get("id") != 2:
                        continue
                    if "error" in message:
                        raise ProviderUnavailableError(
                            f"Codex rate-limit RPC failed: {_safe_error(json.dumps(message['error']))}"
                        )
                    result = message.get("result")
                    if not isinstance(result, dict):
                        raise ProviderUnavailableError("Codex rate-limit RPC returned no object")
                    return result
            detail = _safe_error("".join(errors))
            raise ProviderUnavailableError(
                "Codex rate-limit RPC timed out" + (f": {detail}" if detail else "")
            )
        except (OSError, BrokenPipeError) as exc:
            raise ProviderUnavailableError(f"Codex app-server unavailable: {exc}") from exc
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def _limit_snapshots(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    by_id = result.get("rateLimitsByLimitId")
    if isinstance(by_id, dict) and by_id:
        return {
            str(identifier): dict(snapshot)
            for identifier, snapshot in by_id.items()
            if isinstance(snapshot, dict)
        }
    legacy = result.get("rateLimits")
    if isinstance(legacy, dict):
        identifier = str(legacy.get("limitId") or "default")
        return {identifier: dict(legacy)}
    return {}


def _snapshot_limited(snapshot: Mapping[str, Any]) -> bool:
    if snapshot.get("spendControlReached") is True:
        return True
    reached = snapshot.get("rateLimitReachedType")
    if reached not in (None, "", False):
        return True
    for name in ("primary", "secondary"):
        window = snapshot.get(name)
        if isinstance(window, dict):
            used = window.get("usedPercent")
            if isinstance(used, int) and not isinstance(used, bool) and used >= 100:
                return True
    return False


def _reset_epochs(snapshots: Mapping[str, Mapping[str, Any]]) -> list[int]:
    result: list[int] = []
    for snapshot in snapshots.values():
        for name in ("primary", "secondary"):
            window = snapshot.get(name)
            epoch = window.get("resetsAt") if isinstance(window, dict) else None
            if isinstance(epoch, int) and not isinstance(epoch, bool):
                result.append(epoch)
    return sorted(set(result))


def _public_snapshot(identifier: str, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "limit_id": str(snapshot.get("limitId") or identifier),
        "limit_name": snapshot.get("limitName"),
        "plan_type": snapshot.get("planType"),
        "reached_type": snapshot.get("rateLimitReachedType"),
        "spend_control_reached": snapshot.get("spendControlReached") is True,
        "limited": _snapshot_limited(snapshot),
        "windows": [],
    }
    for role in ("primary", "secondary"):
        window = snapshot.get(role)
        if not isinstance(window, dict):
            continue
        result["windows"].append(
            {
                "role": role,
                "used_percent": window.get("usedPercent"),
                "duration_minutes": window.get("windowDurationMins"),
                "resets_at": window.get("resetsAt"),
            }
        )
    return result


class RateLimitNotifier:
    def __init__(self, messages_dir: Path) -> None:
        resolved = messages_dir.resolve()
        config = replace(
            LabConfig.from_env(),
            repo_root=resolved.parent.parent,
            lab_root=resolved.parent,
            messages_dir=resolved,
        )
        self.store = MessageStore(config)

    def rate_limit(
        self,
        provider: str,
        event_id: str,
        *,
        reset_epochs: Sequence[int] = (),
        detail: str | None = None,
    ) -> None:
        resets = [
            datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
            for epoch in reset_epochs
        ]
        body = (
            f"{provider.title()} reached a rate limit. "
            + (
                "New strategic boundaries will use Fugu until Codex is available again."
                if provider == "codex"
                else "No alternate strategic provider is currently available; the boundary is waiting."
            )
        )
        if resets:
            body += f"\n\nObserved reset time(s): {', '.join(resets)}."
        if detail:
            body += f"\n\nObserved provider response: {_safe_error(detail, 800)}"
        self.store.write_system_notice(
            f"provider-rate-limit:{provider}:{event_id}",
            f"{provider.title()} rate limit reached",
            body,
            metadata={"provider": provider, "reset_epochs": list(reset_epochs)},
        )


class ProviderMonitor:
    def __init__(
        self,
        status_path: Path,
        *,
        reader: CodexRateLimitReader | Callable[[], dict[str, Any]] | None = None,
        notifier: RateLimitNotifier | None = None,
    ) -> None:
        self.status_path = status_path.resolve()
        self.reader = reader or CodexRateLimitReader()
        self.notifier = notifier

    def refresh(self) -> dict[str, Any]:
        previous = _read_object(self.status_path)
        try:
            raw = self.reader.read() if hasattr(self.reader, "read") else self.reader()
            snapshots = _limit_snapshots(raw)
            if not snapshots:
                raise ProviderUnavailableError("Codex returned no rate-limit buckets")
            limited = any(_snapshot_limited(snapshot) for snapshot in snapshots.values())
            reset_epochs = _reset_epochs(snapshots)
            status = {
                "schema_version": STATUS_SCHEMA,
                "observed_at": utc_now(),
                "source": "codex app-server account/rateLimits/read",
                "codex": {
                    "state": "limited" if limited else "available",
                    "limited": limited,
                    "error": None,
                    "buckets": [
                        _public_snapshot(identifier, snapshot)
                        for identifier, snapshot in sorted(snapshots.items())
                    ],
                    "reset_epochs": reset_epochs,
                },
                "fugu": self._fugu_state(previous),
                "selected_provider": "fugu" if limited else "codex",
                "reason": "codex_rate_limited" if limited else "codex_available",
            }
            if limited:
                fingerprint = self._fingerprint(snapshots)
                prior_fingerprint = (
                    previous.get("codex", {}).get("limit_event_id")
                    if isinstance(previous, dict) and isinstance(previous.get("codex"), dict)
                    else None
                )
                status["codex"]["limit_event_id"] = fingerprint
                if fingerprint != prior_fingerprint and self.notifier is not None:
                    self.notifier.rate_limit(
                        "codex",
                        fingerprint,
                        reset_epochs=reset_epochs,
                    )
        except ProviderUnavailableError as exc:
            status = {
                "schema_version": STATUS_SCHEMA,
                "observed_at": utc_now(),
                "source": "codex app-server account/rateLimits/read",
                "codex": {
                    "state": "unknown",
                    "limited": False,
                    "error": _safe_error(str(exc)),
                    "buckets": [],
                    "reset_epochs": [],
                },
                "fugu": self._fugu_state(previous),
                "selected_provider": None,
                "reason": "codex_status_unknown",
            }
        _atomic_json(self.status_path, status)
        return status

    def record_command_limit(self, provider: str, detail: str) -> dict[str, Any]:
        current = _read_object(self.status_path) or {
            "schema_version": STATUS_SCHEMA,
            "observed_at": utc_now(),
            "source": "provider command",
            "codex": {"state": "unknown", "limited": False, "buckets": [], "reset_epochs": []},
            "fugu": {"state": "unknown", "limited": False, "error": None},
            "selected_provider": None,
            "reason": "provider_command",
        }
        event_id = hashlib.sha256(
            f"{provider}:{int(time.time() // 300)}".encode("utf-8")
        ).hexdigest()[:24]
        state = current.setdefault(provider, {})
        if not isinstance(state, dict):
            state = {}
            current[provider] = state
        state.update(
            {
                "state": "limited",
                "limited": True,
                "error": "Provider reported a rate-limit response.",
                "limit_event_id": event_id,
                "retry_after_epoch": (
                    int(time.time()) + 900 if provider == "fugu" else None
                ),
            }
        )
        current["observed_at"] = utc_now()
        current["selected_provider"] = "fugu" if provider == "codex" else None
        current["reason"] = f"{provider}_command_rate_limited"
        _atomic_json(self.status_path, current)
        if self.notifier is not None:
            self.notifier.rate_limit(provider, event_id)
        return current

    @staticmethod
    def _fugu_state(previous: dict[str, Any] | None) -> dict[str, Any]:
        old = previous.get("fugu") if isinstance(previous, dict) else None
        if isinstance(old, dict) and old.get("state") == "limited":
            retry_after = old.get("retry_after_epoch")
            if (
                isinstance(retry_after, int)
                and not isinstance(retry_after, bool)
                and retry_after > time.time()
            ):
                return dict(old)
        return {
            "state": "configured" if os.environ.get("SAKANA_API_KEY") else "unconfigured",
            "limited": False,
            "error": None,
        }

    @staticmethod
    def _fingerprint(snapshots: Mapping[str, Mapping[str, Any]]) -> str:
        boundary = {
            identifier: {
                "reached": snapshot.get("rateLimitReachedType"),
                "spend": snapshot.get("spendControlReached"),
                "resets": _reset_epochs({identifier: snapshot}),
            }
            for identifier, snapshot in sorted(snapshots.items())
            if _snapshot_limited(snapshot)
        }
        return hashlib.sha256(
            json.dumps(boundary, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]


@dataclass(frozen=True, slots=True)
class ProviderExecution:
    provider: str
    model: str
    output: dict[str, Any]
    duration_seconds: float
    failover_reason: str | None


class ProviderRouter:
    """Run one schema-bound read-only strategic model call."""

    def __init__(
        self,
        monitor: ProviderMonitor,
        *,
        repo_root: Path,
        codex_executable: str = "/home/aomukai/.local/bin/codex",
        fugu_executable: str = "/home/aomukai/.local/bin/codex-fugu",
        codex_model: str = "gpt-5.6-sol",
        strategic_provider: str = "codex_fugu",
        openrouter_model: str = OPENROUTER_STRATEGIC_MODEL,
        openrouter_base_url: str = OPENROUTER_CHAT_COMPLETIONS_URL,
        openrouter_api_key_env: str = "OPENROUTER_API_KEY",
        deepseek_model: str = DEEPSEEK_STRATEGIC_MODEL,
        deepseek_base_url: str = DEEPSEEK_CHAT_COMPLETIONS_URL,
        deepseek_api_key_env: str = "DEEPSEEK_API_KEY",
        openrouter_max_tokens: int = 8192,
        timeout_seconds: int = 1200,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        remote_opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.monitor = monitor
        self.repo_root = repo_root.resolve()
        self.codex_executable = codex_executable
        self.fugu_executable = fugu_executable
        self.codex_model = codex_model
        if strategic_provider not in STRATEGIC_PROVIDER_OPTIONS:
            raise ValueError(
                "strategic_provider must be one of "
                + ", ".join(sorted(STRATEGIC_PROVIDER_OPTIONS))
            )
        if openrouter_max_tokens < 1:
            raise ValueError("openrouter_max_tokens must be positive")
        self.strategic_provider = strategic_provider
        self.openrouter_model = openrouter_model
        self.openrouter_base_url = openrouter_base_url
        self.openrouter_api_key_env = openrouter_api_key_env
        self.deepseek_model = deepseek_model
        self.deepseek_base_url = deepseek_base_url
        self.deepseek_api_key_env = deepseek_api_key_env
        self.openrouter_max_tokens = openrouter_max_tokens
        self.timeout_seconds = timeout_seconds
        self.command_runner = command_runner
        self.remote_opener = remote_opener

    def run(self, prompt: str, output_schema: Path) -> ProviderExecution:
        if self.strategic_provider in ("openrouter", "deepseek"):
            provider_name, base_url, model, api_key_env = self._remote_config()
            return self._invoke_remote(
                provider_name,
                base_url,
                model,
                api_key_env,
                prompt,
                output_schema,
                None,
            )
        status = self.monitor.refresh()
        codex_state = status.get("codex", {}).get("state")
        fugu_state = status.get("fugu", {}).get("state")
        if codex_state == "limited":
            if fugu_state == "limited":
                raise BothProvidersLimitedError("Codex and Fugu are rate-limited")
            try:
                return self._invoke("fugu", prompt, output_schema, "codex_rate_limited")
            except ProviderUnavailableError as exc:
                if is_rate_limit_error(str(exc)):
                    raise BothProvidersLimitedError(
                        "Codex and Fugu are rate-limited"
                    ) from exc
                raise
        if codex_state != "available":
            raise ProviderUnavailableError(
                "Codex rate-limit state is unknown; refusing to guess and double-spend"
            )
        try:
            return self._invoke("codex", prompt, output_schema, None)
        except ProviderUnavailableError as exc:
            if not is_rate_limit_error(str(exc)):
                raise
            self.monitor.record_command_limit("codex", str(exc))
            try:
                return self._invoke(
                    "fugu",
                    prompt,
                    output_schema,
                    "codex_command_rate_limited",
                )
            except ProviderUnavailableError as fugu_exc:
                if is_rate_limit_error(str(fugu_exc)):
                    raise BothProvidersLimitedError(
                        "Codex and Fugu are rate-limited"
                    ) from fugu_exc
                raise

    def _invoke(
        self,
        provider: str,
        prompt: str,
        output_schema: Path,
        failover_reason: str | None,
    ) -> ProviderExecution:
        if provider == "codex":
            command = [
                self.codex_executable,
                "--ask-for-approval",
                "never",
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--model",
                self.codex_model,
            ]
            model = self.codex_model
            environment = None
        else:
            command = [
                self.fugu_executable,
                "--no-update",
                "--ask-for-approval",
                "never",
                "exec",
                "--ephemeral",
            ]
            model = "fugu"
            environment = dict(os.environ)
            environment["CODEX_FUGU_NO_NOTICE"] = "1"
            environment["CODEX_FUGU_NO_UPDATE"] = "1"
        command.extend(
            [
                "--sandbox",
                "read-only",
                "--output-schema",
                str(output_schema.resolve()),
                "--color",
                "never",
                "-C",
                str(self.repo_root),
                "-",
            ]
        )
        started = time.monotonic()
        try:
            completed = self.command_runner(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                **({"env": environment} if environment is not None else {}),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderUnavailableError(f"{provider} invocation failed: {exc}") from exc
        combined = "\n".join((completed.stderr or "", completed.stdout or ""))
        if completed.returncode != 0:
            if is_rate_limit_error(combined):
                self.monitor.record_command_limit(provider, combined)
            raise ProviderUnavailableError(
                f"{provider} invocation exited {completed.returncode}: {_failure_summary(combined)}"
            )
        try:
            output = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(f"{provider} returned invalid JSON") from exc
        if not isinstance(output, dict):
            raise ProviderUnavailableError(f"{provider} returned a non-object response")
        return ProviderExecution(
            provider=provider,
            model=model,
            output=output,
            duration_seconds=round(time.monotonic() - started, 3),
            failover_reason=failover_reason,
        )

    def _remote_config(self) -> tuple[str, str, str, str]:
        if self.strategic_provider == "openrouter":
            return (
                "openrouter",
                self.openrouter_base_url,
                self.openrouter_model,
                self.openrouter_api_key_env,
            )
        return (
            "deepseek",
            self.deepseek_base_url,
            self.deepseek_model,
            self.deepseek_api_key_env,
        )

    def _invoke_remote(
        self,
        provider_name: str,
        base_url: str,
        model: str,
        api_key_env: str,
        prompt: str,
        output_schema: Path,
        failover_reason: str | None,
    ) -> ProviderExecution:
        environment = _environment_with_dotenv(
            self.repo_root,
            {api_key_env},
        )
        key = environment.get(api_key_env)
        if not key:
            raise ProviderUnavailableError(
                f"{api_key_env} is unavailable in the environment or repository .env"
            )
        try:
            schema_text = output_schema.resolve().read_text(encoding="utf-8")
        except OSError as exc:
            raise ProviderUnavailableError(
                f"strategic output schema is unavailable: {exc}"
            ) from exc
        request_prompt = (
            f"{prompt}\n\n"
            "OUTPUT CONTRACT\n"
            "Return only one JSON object. Do not include markdown fences, commentary, "
            "or any non-JSON text. The object must conform to this JSON schema:\n"
            f"{schema_text}"
        )
        request_body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a schema-bound strategic orchestrator. Return exactly "
                        "one JSON object and no prose outside that object."
                    ),
                },
                {"role": "user", "content": request_prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if provider_name == "openrouter":
            # DeepSeek V4 Flash currently defaults to high reasoning on OpenRouter.
            # Bound it so a large strategic prompt cannot spend the whole completion
            # allowance on reasoning and return an empty schema-bound answer.
            request_body["reasoning"] = {"effort": "low", "exclude": True}
        else:
            request_body["max_tokens"] = self.openrouter_max_tokens
        if provider_name == "deepseek" and model.startswith("deepseek-v4"):
            # DeepSeek V4 Flash exposes an explicit reasoning toggle; strategic
            # decisions are schema-bound, so keep it deterministic.
            request_body["thinking"] = {"type": "disabled"}
        request = Request(
            base_url,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Title": "Ninereeds Strategic Orchestrator",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with self.remote_opener(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            combined = f"HTTP {exc.code}: {detail}"
            if exc.code == 429 or is_rate_limit_error(combined):
                self.monitor.record_command_limit(provider_name, combined)
            raise ProviderUnavailableError(
                f"{provider_name} invocation failed: {_failure_summary(combined)}"
            ) from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError(
                f"{provider_name} invocation failed: {_safe_error(str(exc))}"
            ) from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailableError(
                f"{provider_name} returned an unexpected response shape"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            choice = payload.get("choices", [{}])[0]
            usage = payload.get("usage")
            completion_tokens = (
                usage.get("completion_tokens") if isinstance(usage, dict) else None
            )
            raise ProviderUnavailableError(
                f"{provider_name} returned empty content "
                f"(finish_reason={choice.get('finish_reason')!r}, "
                f"completion_tokens={completion_tokens!r})"
            )
        try:
            output = _json_object_from_text(content)
        except (json.JSONDecodeError, ProviderUnavailableError) as exc:
            raise ProviderUnavailableError(
                f"{provider_name} returned invalid JSON"
            ) from exc
        return ProviderExecution(
            provider=provider_name,
            model=model,
            output=output,
            duration_seconds=round(time.monotonic() - started, 3),
            failover_reason=failover_reason,
        )


def default_monitor(control_root: Path, repo_root: Path) -> ProviderMonitor:
    # Provider hiccups that recover through routing stay silent. The supervisor's
    # emergency policy owns human notification after immediate recovery fails.
    return ProviderMonitor(control_root.resolve() / "provider/status.json")
