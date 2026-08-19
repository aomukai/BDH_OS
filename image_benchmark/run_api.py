from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from image_benchmark.common import PROMPT, parse_response, semantic_contract_errors
from image_registry.cli import connect


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--token-env")
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--selection", default="benchmark-100")
    parser.add_argument("--db", type=Path, default=Path("training_data/image_registry/registry.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    token = os.environ.get(args.token_env, "") if args.token_env else ""
    if args.token_env and len(token) < 32:
        raise SystemExit(f"missing credential in {args.token_env}")

    completed: set[str] = set()
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            completed.add(json.loads(line)["source_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with connect(args.db) as db:
        rows = db.execute(
            """SELECT s.ordinal, a.source_id, a.local_path FROM selection s
               JOIN asset a ON a.id=s.asset_id WHERE s.name=? ORDER BY s.ordinal""",
            (args.selection,),
        ).fetchall()
    if args.limit is not None:
        rows = rows[:args.limit]

    with args.output.open("a", encoding="utf-8", buffering=1) as output:
        for index, row in enumerate(rows, 1):
            if row["source_id"] in completed:
                continue
            pixels = base64.b64encode(Path(row["local_path"]).read_bytes()).decode("ascii")
            payload = {
                "model": args.model,
                "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + pixels}},
                    {"type": "text", "text": PROMPT},
                ]}],
                "max_tokens": 512,
            }
            if args.disable_thinking:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            request = urllib.request.Request(
                args.endpoint, data=json.dumps(payload).encode("utf-8"),
                headers=headers,
            )
            started = time.perf_counter()
            raw = ""
            error = None
            usage = None
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(request, timeout=args.timeout) as response:
                        document = json.load(response)
                    raw = document["choices"][0]["message"]["content"]
                    usage = document.get("usage")
                    break
                except (urllib.error.URLError, KeyError, ValueError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
            elapsed = time.perf_counter() - started
            parsed, errors = parse_response(raw) if raw else (None, ["request:" + str(error)])
            record = {
                "selection": args.selection,
                "ordinal": row["ordinal"],
                "source_id": row["source_id"],
                "model": args.model_name,
                "model_id": args.model,
                "prompt_version": "visual-audit-v1",
                "inference_seconds": elapsed,
                "raw": raw,
                "parsed": parsed,
                "schema_errors": errors,
                "semantic_contract_errors": semantic_contract_errors(parsed),
                "request_error": error if not raw else None,
                "usage": usage,
            }
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            print(f'{index}/{len(rows)} {row["source_id"]} {elapsed:.2f}s schema={"ok" if not errors else errors}', flush=True)


if __name__ == "__main__":
    main()
