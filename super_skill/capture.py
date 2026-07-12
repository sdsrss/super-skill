"""Append-only JSONL event WAL (docs/01 FR-CAP-1, WS form).

Every event is redacted before it is written (capture.append never persists a raw
payload), then appended as one JSON line under events/<date>/events.jsonl. Raw
events are TTL-bounded (FR-CAP-6); structured products live elsewhere.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

from . import config
from .redact import redact_payload, redact_text
from .schemas import CaptureEvent, EventType


class EventLog:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or config.state_root()
        self.events_dir = self.root / "events"

    def _new_id(self) -> str:
        return uuid.uuid4().hex

    def append(
        self,
        event_type: EventType,
        session_id: str,
        payload: dict[str, object],
        *,
        project_id: str | None = None,
        event_id: str | None = None,
        consent_scope: str = "default",
    ) -> CaptureEvent:
        """Redact then append. Returns the persisted (redacted) event.

        Every field that can carry private content — the payload AND the
        project_id (derived from cwd, often a home path) — is redacted here so
        nothing raw reaches disk (FR-CAP-2, §8 SAFETY)."""
        red_payload, marks = redact_payload(payload)
        red_project = redact_text(project_id)[0] if project_id else None
        event = CaptureEvent(
            event_id=event_id or self._new_id(),
            session_id=session_id,
            event_type=event_type,
            project_id=red_project,
            payload=red_payload,
            redactions=marks,
            consent_scope=consent_scope,
        )
        day = event.timestamp.strftime("%Y-%m-%d")
        out = self.events_dir / day / "events.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
        return event

    def iter_events(self) -> Iterator[CaptureEvent]:
        if not self.events_dir.exists():
            return
        for day in sorted(self.events_dir.iterdir()):
            wal = day / "events.jsonl"
            if not wal.exists():
                continue
            for line in wal.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    yield CaptureEvent.model_validate_json(line)

    def count(self) -> int:
        return sum(1 for _ in self.iter_events())
