from __future__ import annotations

import argparse
import json
from pathlib import Path

from image_registry.cli import DEFAULT_DB, connect
from image_registry.review_queue import (
    claim_batch,
    complete_claim,
    create_queue,
    export_filename_list,
    export_results,
    fail_claim,
    queue_status,
    register_worker,
    renew_claim,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Leased image-review work queue")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create")
    create.add_argument("queue")
    create.add_argument("--selection", required=True)

    register = commands.add_parser("register-worker")
    register.add_argument("queue")
    register.add_argument("worker")
    register.add_argument("--backend", required=True)
    register.add_argument("--model", required=True)
    register.add_argument("--max-claims", type=int, required=True)

    claim = commands.add_parser("claim")
    claim.add_argument("queue")
    claim.add_argument("worker")
    claim.add_argument("--count", type=int)
    claim.add_argument("--lease-seconds", type=int, default=1800)

    renew = commands.add_parser("renew")
    renew.add_argument("token")
    renew.add_argument("worker")
    renew.add_argument("--lease-seconds", type=int, default=1800)

    complete = commands.add_parser("complete")
    complete.add_argument("token")
    complete.add_argument("worker")
    complete.add_argument("result", type=Path)

    fail = commands.add_parser("fail")
    fail.add_argument("token")
    fail.add_argument("worker")
    fail.add_argument("error")
    fail.add_argument("--terminal", action="store_true")

    status = commands.add_parser("status")
    status.add_argument("queue")

    export_list = commands.add_parser("export-list")
    export_list.add_argument("queue")
    export_list.add_argument("output", type=Path)

    export_done = commands.add_parser("export-results")
    export_done.add_argument("queue")
    export_done.add_argument("output", type=Path)

    args = parser.parse_args()
    with connect(args.db) as db:
        if args.command == "create":
            print(json.dumps({"created": create_queue(db, args.queue, args.selection)}))
        elif args.command == "register-worker":
            register_worker(
                db, args.queue, args.worker, args.backend, args.model, args.max_claims
            )
        elif args.command == "claim":
            print(json.dumps(
                claim_batch(db, args.queue, args.worker, args.count, args.lease_seconds),
                ensure_ascii=False, sort_keys=True,
            ))
        elif args.command == "renew":
            print(json.dumps({"lease_expires_at": renew_claim(
                db, args.token, args.worker, args.lease_seconds
            )}))
        elif args.command == "complete":
            complete_claim(
                db, args.token, args.worker,
                json.loads(args.result.read_text(encoding="utf-8")),
            )
        elif args.command == "fail":
            fail_claim(
                db, args.token, args.worker, {"message": args.error},
                retry=not args.terminal,
            )
        elif args.command == "status":
            print(json.dumps(queue_status(db, args.queue), ensure_ascii=False, sort_keys=True))
        elif args.command in {"export-list", "export-results"}:
            rows = (
                export_filename_list(db, args.queue)
                if args.command == "export-list"
                else export_results(db, args.queue)
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
