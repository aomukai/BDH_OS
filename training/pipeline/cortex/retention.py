from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY_SCHEMA = "ninereeds_cortex_checkpoint_registry_v1"
POLICY_SCHEMA = "ninereeds_cortex_retention_policy_v1"
DEFAULT_CHECKPOINT_BYTES = 8 * 1024**3


class RetentionError(RuntimeError):
    pass


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_policy(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != POLICY_SCHEMA
        or not 0 < float(value.get("warning_used_fraction", 0)) < 1
        or not 0 < float(value.get("prune_used_fraction", 0)) < 1
        or not 0 < float(value.get("critical_used_fraction", 0)) < 1
    ):
        raise RetentionError("invalid Cortex retention policy")
    if not (
        value["warning_used_fraction"]
        < value["prune_used_fraction"]
        < value["critical_used_fraction"]
    ):
        raise RetentionError("retention watermarks must be strictly increasing")
    return value


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": REGISTRY_SCHEMA,
            "updated_at": utc_now(),
            "checkpoints": {},
            "events": [],
        }
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != REGISTRY_SCHEMA
        or not isinstance(value.get("checkpoints"), dict)
        or not isinstance(value.get("events"), list)
    ):
        raise RetentionError("invalid Cortex checkpoint registry")
    return value


def write_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = utc_now()
    payload = json.dumps(
        registry, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def record_certificate(
    registry_path: Path,
    *,
    campaign_id: str,
    certificate: dict[str, Any],
    checkpoint_root: Path,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    relative = certificate["candidate_checkpoint"]
    candidate = (checkpoint_root / relative).resolve()
    root = checkpoint_root.resolve()
    if root != candidate and root not in candidate.parents:
        raise RetentionError("candidate checkpoint escapes repository root")
    parent = certificate["parent_checkpoint"]
    entry = {
        "path": relative,
        "sha256": certificate["candidate_sha256"],
        "parent": parent,
        "parent_sha256": certificate["parent_sha256"],
        "campaign_id": campaign_id,
        "state": certificate["status"],
        "rollback_target": certificate["rollback_target"],
        "evaluated_at": utc_now(),
        "size_bytes": candidate.stat().st_size if candidate.is_file() else None,
        "pinned": False,
        "certificate": certificate,
    }
    registry["checkpoints"][relative] = entry
    registry["events"] = (
        registry["events"]
        + [
            {
                "at": entry["evaluated_at"],
                "event": f"candidate_{entry['state']}",
                "path": relative,
                "campaign_id": campaign_id,
            }
        ]
    )[-500:]
    write_registry(registry_path, registry)
    return entry


def disk_status(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    used = usage.total - usage.free
    return {
        "total_bytes": usage.total,
        "used_bytes": used,
        "free_bytes": usage.free,
        "used_fraction": used / usage.total,
    }


def prune_if_needed(
    *,
    checkpoint_root: Path,
    registry_path: Path,
    policy_path: Path,
    protected_paths: set[str],
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    before = disk_status(checkpoint_root)
    result = {
        "triggered": False,
        "before": before,
        "after": before,
        "deleted": [],
        "reclaimed_bytes": 0,
    }
    if (
        not policy.get("automatic_pruning", False)
        or before["used_fraction"] < policy["prune_used_fraction"]
    ):
        return result
    result["triggered"] = True
    registry = load_registry(registry_path)
    entries = list(registry["checkpoints"].values())
    developmental = [
        entry
        for entry in entries
        if entry.get("state") == "developmental_progress"
    ]
    developmental.sort(
        key=lambda row: str(row.get("evaluated_at") or ""), reverse=True
    )
    retained_developmental = {
        str(entry["path"])
        for entry in developmental[
            : int(policy.get("keep_developmental_checkpoints", 3))
        ]
    }
    latest_developmental = developmental[:1]
    lineage_protected = {
        str(entry["rollback_target"])
        for entry in [
            *(
                row
                for row in entries
                if row.get("state") in {"admitted", "quarantine"}
            ),
            *latest_developmental,
        ]
        if entry.get("rollback_target")
    }
    protected_paths = set(protected_paths) | lineage_protected
    admitted = [
        entry for entry in entries if entry.get("state") == "admitted"
    ]
    admitted.sort(key=lambda row: str(row.get("evaluated_at") or ""), reverse=True)
    retained_winners = {
        str(entry["path"])
        for entry in admitted[: int(policy["keep_campaign_winners"])]
    }
    rejected_by_campaign: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if entry.get("state") in {"rejected", "retired"}:
            rejected_by_campaign.setdefault(
                str(entry.get("campaign_id") or "unknown"), []
            ).append(entry)
    retained_rejected: set[str] = set()
    keep_count = int(policy["keep_rejected_per_campaign"])
    for values in rejected_by_campaign.values():
        values.sort(key=lambda row: str(row.get("evaluated_at") or ""), reverse=True)
        retained_rejected.update(
            str(row["path"]) for row in values[:keep_count]
        )
    candidates = [
        entry
        for entry in entries
        if (
            entry.get("state") in {"rejected", "retired"}
            or (
                entry.get("state") == "developmental_progress"
                and entry.get("path") not in retained_developmental
            )
            or (
                entry.get("state") == "admitted"
                and entry.get("path") not in retained_winners
            )
        )
        and not entry.get("pinned")
        and entry.get("path") not in protected_paths
        and entry.get("path") not in retained_rejected
    ]
    candidates.sort(key=lambda row: str(row.get("evaluated_at") or ""))
    for entry in candidates:
        if disk_status(checkpoint_root)["used_fraction"] <= policy[
            "warning_used_fraction"
        ]:
            break
        relative = str(entry["path"])
        target = (checkpoint_root / relative).resolve()
        root = checkpoint_root.resolve()
        if root not in target.parents or target.suffix != ".pt" or not target.is_file():
            continue
        size = target.stat().st_size
        target.unlink()
        entry["state"] = "deleted"
        entry["deleted_at"] = utc_now()
        result["deleted"].append(relative)
        result["reclaimed_bytes"] += size
        registry["events"].append(
            {
                "at": entry["deleted_at"],
                "event": "checkpoint_deleted",
                "path": relative,
                "reclaimed_bytes": size,
            }
        )
    registry["events"] = registry["events"][-500:]
    write_registry(registry_path, registry)
    result["after"] = disk_status(checkpoint_root)
    return result


def ensure_training_headroom(
    *,
    checkpoint_root: Path,
    parent_checkpoint: Path | None,
    output_checkpoint: Path,
    registry_path: Path,
    policy_path: Path,
) -> dict[str, Any]:
    protected = {
        path
        for path in (
            _relative_or_none(parent_checkpoint, checkpoint_root),
            _relative_or_none(output_checkpoint, checkpoint_root),
        )
        if path is not None
    }
    pruning = prune_if_needed(
        checkpoint_root=checkpoint_root,
        registry_path=registry_path,
        policy_path=policy_path,
        protected_paths=protected,
    )
    policy = load_policy(policy_path)
    status = disk_status(checkpoint_root)
    expected = (
        parent_checkpoint.stat().st_size
        if parent_checkpoint is not None and parent_checkpoint.is_file()
        else DEFAULT_CHECKPOINT_BYTES
    )
    required = max(
        int(policy["minimum_free_bytes"]),
        int(expected * float(policy["checkpoint_headroom_multiplier"])),
    )
    problems = []
    if status["used_fraction"] >= policy["critical_used_fraction"]:
        problems.append(
            f"filesystem is {status['used_fraction']:.1%} used, at or above the "
            f"{policy['critical_used_fraction']:.0%} critical watermark"
        )
    if status["free_bytes"] < required:
        problems.append(
            f"{status['free_bytes']} free bytes is below required training "
            f"headroom {required}"
        )
    if problems:
        raise RetentionError("; ".join(problems))
    return {
        "disk": status,
        "expected_checkpoint_bytes": expected,
        "required_free_bytes": required,
        "warning": status["used_fraction"] >= policy["warning_used_fraction"],
        "pruning": pruning,
    }


def _relative_or_none(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
