"""Report-only DeepSeek audit of one frozen visual foundation manifest."""

from __future__ import annotations

import argparse
import base64
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request

from PIL import Image


SCHEMA_VERSION = "ninereeds_deepseek_foundation_audit_v1"
DEFAULT_MODEL = "deepseek-v4-flash-vision-exp"
DEFAULT_ENDPOINT = "https://api.deepseek.com/chat/completions"


SYSTEM = """You are an independent, report-only auditor of a frozen visual vocabulary corpus.
You have no authority to delete, replace, regenerate, or mutate anything. Inspect the locked
lexical sense and all ten numbered images. Prior reviewer verdicts are deliberately withheld.

Check the lexical contract first: the label must have a defined positive meaning and its declared
part of speech must match that exact meaning. Then check every image for direct sense fit, central
visible evidence, text or watermark problems, malformed content, distracting defects, and stable
shortcut confounders. Finally check the ten-image pack for consistent sense, useful variation,
duplicates, and repeated incidental shortcuts. A visible spelling of the target is not by itself
evidence for the locked meaning. For homographs, reject images that show a different grammatical
or lexical sense even when the same letters are visible.

Return one JSON object only with this shape:
{
  "contract_id": "...",
  "lexical": {"verdict": "PASS|FAIL|UNCERTAIN", "explanation": "..."},
  "images": [
    {"index": 1, "asset_sha256": "...", "verdict": "PASS|FAIL|UNCERTAIN",
     "visible_evidence": "...", "sense_fit_explanation": "...",
     "defect_codes": ["..."], "confidence": "high|medium|low"}
  ],
  "pack": {"verdict": "PASS|FAIL|UNCERTAIN", "variation_verdict": "PASS|FAIL|UNCERTAIN",
    "confounders": ["..."], "weakest_image_indexes": [1], "recommended_review_action": "..."},
  "overall_verdict": "PASS|FAIL|UNCERTAIN"
}
Include each numbered image exactly once. Do not add markdown or commentary outside JSON."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def manifest_sha256(curriculum: Path) -> str:
    digest = hashlib.sha256()
    for name in ("teaching-contracts.jsonl", "accepted-assets.jsonl", "dependency-edges.jsonl"):
        path = curriculum / name
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def prompt(contract: dict[str, Any], assets: list[dict[str, Any]], manifest: str) -> str:
    context = {
        "input_manifest_sha256": manifest,
        "contract_id": contract["contract_id"],
        "canonical_label": contract["display_label"],
        "lemma": contract.get("lemma"),
        "part_of_speech": contract["part_of_speech"],
        "locked_teaching_sense": contract["teaching_sense"],
        "images": [{
            "index": row["exposure_index"],
            "asset_sha256": str(row.get("sha256") or row.get("asset_sha256")),
            "literal_caption": row.get("literal_caption") or row.get("caption"),
            "source_caption": row.get("source_caption"),
            "source": row.get("source"),
            "visible_text_declared": row.get("visible_text"),
        } for row in assets],
    }
    return "Audit this exact frozen contract and pack:\n" + json.dumps(context, ensure_ascii=False, sort_keys=True)


def data_url(path: Path) -> tuple[str, dict[str, Any]]:
    """Encode an audit image, bounding only the API transport representation.

    The frozen source remains untouched and its original digest remains the image
    identity. Large files are resized in memory to keep a ten-image request below
    the provider's request-size limit.
    """
    source = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    transport: dict[str, Any] = {"resized": False, "source_bytes": len(source)}
    with Image.open(BytesIO(source)) as opened:
        dimensions = list(opened.size)
        should_resize = len(source) > 1_000_000 or max(opened.size) > 1024
        if should_resize:
            image = opened.convert("RGB")
            original_size = list(image.size)
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            encoded = BytesIO()
            image.save(encoded, format="JPEG", quality=88, optimize=True)
            source = encoded.getvalue()
            mime = "image/jpeg"
            transport.update({
                "resized": True,
                "original_dimensions": original_size,
                "transport_dimensions": list(image.size),
                "transport_bytes": len(source),
            })
        else:
            transport["original_dimensions"] = dimensions
    if not transport["resized"]:
        transport["transport_bytes"] = len(source)
    return f"data:{mime};base64," + base64.b64encode(source).decode("ascii"), transport


def validate(result: dict[str, Any], contract: dict[str, Any], assets: list[dict[str, Any]]) -> None:
    verdicts = {"PASS", "FAIL", "UNCERTAIN"}
    if result.get("contract_id") != contract["contract_id"]:
        raise ValueError("contract_id mismatch")
    result["overall_verdict"] = str(result.get("overall_verdict", "")).upper()
    if result["overall_verdict"] not in verdicts:
        raise ValueError("invalid overall verdict")
    images = result.get("images")
    if not isinstance(images, list) or len(images) != len(assets):
        raise ValueError("response does not contain every image")
    expected = {
        int(row["exposure_index"]): str(row.get("sha256") or row.get("asset_sha256"))
        for row in assets
    }
    actual_indexes = [int(row["index"]) for row in images]
    if set(actual_indexes) != set(expected) or len(actual_indexes) != len(set(actual_indexes)):
        raise ValueError("image index mismatch")
    for row in images:
        index = int(row["index"])
        row["index"] = index
        row["verdict"] = str(row.get("verdict", "")).upper()
        if row["verdict"] not in verdicts:
            raise ValueError("invalid image verdict")
        # Hashes are manifest identity, not model judgment. Anchor them to the
        # numbered inputs even if the model mistypes a long digest.
        row["asset_sha256"] = expected[index]


def review_one(
    contract: dict[str, Any], assets: list[dict[str, Any]], *, output: Path,
    manifest: str, endpoint: str, model: str, api_key: str, retries: int,
) -> dict[str, Any]:
    result_path = output / "concepts" / f"{contract['contract_id']}.json"
    if result_path.is_file():
        return json.loads(result_path.read_text(encoding="utf-8"))
    claim_path = output / "claims" / f"{contract['contract_id']}.lock"
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 7200
    while True:
        try:
            descriptor = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if result_path.is_file():
                return json.loads(result_path.read_text(encoding="utf-8"))
            try:
                owner = json.loads(claim_path.read_text(encoding="utf-8"))
                owner_pid = int(owner["pid"])
                os.kill(owner_pid, 0)
            except ProcessLookupError:
                # A service restart can bypass the claiming thread's finally
                # block. Reclaim only locks whose recorded process is dead.
                claim_path.unlink(missing_ok=True)
                continue
            except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                # The owner may still be writing or releasing the claim.
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f"timed out waiting for claimed audit result: {contract['contract_id']}")
            # The claiming worker may fail and release the lock. Retry acquisition
            # so this worker can take over instead of waiting until the deadline.
            time.sleep(2)
    with os.fdopen(descriptor, "w", encoding="utf-8") as claim:
        claim.write(json.dumps({"contract_id": contract["contract_id"], "pid": os.getpid(), "claimed_at": now()}) + "\n")
    try:
        return _review_claimed(
            contract, assets, output=output, manifest=manifest, endpoint=endpoint,
            model=model, api_key=api_key, retries=retries, result_path=result_path,
        )
    finally:
        claim_path.unlink(missing_ok=True)


def _review_claimed(
    contract: dict[str, Any], assets: list[dict[str, Any]], *, output: Path,
    manifest: str, endpoint: str, model: str, api_key: str, retries: int,
    result_path: Path,
) -> dict[str, Any]:
    text = prompt(contract, assets, manifest)
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    request_images = []
    for row in assets:
        path = Path(row["local_path"])
        digest = str(row.get("sha256") or row.get("asset_sha256"))
        if sha256(path) != digest:
            raise ValueError(f"image changed before audit: {path}")
        content.append({"type": "text", "text": f"IMAGE {row['exposure_index']}"})
        encoded_url, transport = data_url(path)
        content.append({"type": "image_url", "image_url": {"url": encoded_url}})
        request_images.append({
            "index": row["exposure_index"], "path": str(path), "sha256": digest,
            "transport": transport,
        })
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
        "temperature": 0.0,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "max_tokens": 8192,
        "stream": False,
        "user_id": "ninereeds-foundation-independent-audit-v1",
    }
    request_record = {
        "schema_version": SCHEMA_VERSION, "contract_id": contract["contract_id"],
        "manifest_sha256": manifest, "model": model, "endpoint": endpoint,
        "system": SYSTEM, "prompt": text, "images": request_images,
        "settings": {key: body[key] for key in ("temperature", "thinking", "reasoning_effort", "response_format", "max_tokens", "stream")},
    }
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                endpoint, data=json.dumps(body).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            started = time.monotonic()
            with urllib.request.urlopen(request, timeout=300) as response:
                response_document = json.loads(response.read())
            raw = response_document["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            validate(parsed, contract, assets)
            record = {
                **request_record, "attempt": attempt, "created_at": now(),
                "duration_seconds": round(time.monotonic() - started, 3),
                "usage": response_document.get("usage", {}), "raw_response": raw,
                "audit": parsed,
            }
            atomic_json(result_path, record)
            return record
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            last = RuntimeError(f"HTTP {exc.code}: {detail}")
            time.sleep(min(30, attempt * 5))
        except Exception as exc:
            last = exc
            time.sleep(min(30, attempt * 5))
    raise RuntimeError(f"DeepSeek audit failed for {contract['contract_id']}: {last}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curriculum", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract-id", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    args = parser.parse_args()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    manifest = manifest_sha256(args.curriculum)
    contracts = load_jsonl(args.curriculum / "teaching-contracts.jsonl")
    assets = load_jsonl(args.curriculum / "accepted-assets.jsonl")
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in assets:
        by_contract.setdefault(str(row["contract_id"]), []).append(row)
    if args.contract_id:
        selected = set(args.contract_id)
        contracts = [row for row in contracts if row["contract_id"] in selected]
    if args.reverse:
        contracts.reverse()
    if args.limit is not None:
        contracts = contracts[:args.limit]
    jobs = []
    for contract in contracts:
        rows = sorted(by_contract[contract["contract_id"]], key=lambda row: int(row["exposure_index"]))
        if len(rows) != 10:
            raise ValueError(f"{contract['contract_id']} has {len(rows)} images")
        jobs.append((contract, rows))
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                review_one, contract, rows, output=args.output, manifest=manifest,
                endpoint=args.endpoint, model=args.model, api_key=api_key, retries=args.retries,
            ): contract["contract_id"]
            for contract, rows in jobs
        }
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            print(json.dumps({"contract_id": futures[future], "verdict": record["audit"]["overall_verdict"]}), flush=True)
    verdicts = {value: sum(record["audit"]["overall_verdict"] == value for record in records) for value in ("PASS", "FAIL", "UNCERTAIN")}
    summary = {
        "schema_version": SCHEMA_VERSION, "created_at": now(), "report_only": True,
        "manifest_sha256": manifest, "model": args.model, "requested_contracts": len(jobs),
        "completed_contracts": len(records), "verdicts": verdicts,
    }
    atomic_json(args.output / "audit-summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
