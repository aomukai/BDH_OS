from __future__ import annotations

import hashlib
import time
from pathlib import Path

from lab.backend.config import LabConfig
from lab.backend.models import Message


class MessageStore:
    def __init__(self, config: LabConfig) -> None:
        self.config = config

    def list_messages(self, box: str) -> list[Message]:
        box_dir = self._box_dir(box)
        messages: list[Message] = []
        for path in sorted(box_dir.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in {".md", ".txt", ".json"}:
                continue
            messages.append(self._message_from_path(path, box))
        return messages

    def write_outbox(self, title: str, body: str) -> Message:
        timestamp = time.time()
        safe_title = "".join(ch if ch.isalnum() else "-" for ch in title.lower()).strip("-")[:48] or "message"
        path = self._box_dir("outbox") / f"{time.strftime('%Y%m%d-%H%M%S')}-{safe_title}.md"
        content = f"# {title.strip() or 'Untitled'}\n\n{body.strip()}\n"
        path.write_text(content, encoding="utf-8")
        return self._message_from_path(path, "outbox", timestamp=timestamp)

    def _box_dir(self, box: str) -> Path:
        if box not in {"inbox", "outbox"}:
            raise ValueError("box must be inbox or outbox")
        path = self.config.messages_dir / box
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _message_from_path(self, path: Path, box: str, timestamp: float | None = None) -> Message:
        body = path.read_text(encoding="utf-8", errors="replace")
        title = path.stem
        for line in body.splitlines():
            clean = line.strip()
            if clean.startswith("#"):
                title = clean.strip("# ").strip() or title
                break
            if clean:
                title = clean[:80]
                break
        relative = path.relative_to(self.config.repo_root).as_posix()
        message_id = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16]
        return Message(
            id=message_id,
            box=box,
            path=relative,
            title=title,
            body=body,
            timestamp=timestamp if timestamp is not None else path.stat().st_mtime,
        )
