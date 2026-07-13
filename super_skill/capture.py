"""Append-only JSONL event WAL (docs/01 FR-CAP-1, WS form).

Every event is redacted before it is written (capture.append never persists a raw
payload), then appended as one JSON line under events/<date>/events.jsonl. Raw
events are pruned to a TTL by ``prune`` (FR-CAP-6); structured products live
elsewhere.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from . import config
from .redact import redact_payload, redact_text
from .schemas import CaptureEvent, EventType, utcnow


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
        # One atomic append per event: a single O_APPEND os.write, not a buffered
        # writer that can split a large line into multiple write() calls and let
        # two concurrent captures interleave into a corrupt line (H4).
        data = (event.model_dump_json() + "\n").encode("utf-8")
        # 0o600: the WAL holds redacted-but-private session content — never
        # world/group-readable on a multi-user host (audit P2-1).
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            # Loop on short writes so a very large line isn't silently truncated.
            while data:
                data = data[os.write(fd, data):]
        finally:
            os.close(fd)
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
                if not line:
                    continue
                try:
                    yield CaptureEvent.model_validate_json(line)
                except ValidationError:
                    # A killed hook can leave a torn final line; one bad record
                    # must not brick every reader (status/mine/count). Skip it.
                    continue

    def count(self) -> int:
        return sum(1 for _ in self.iter_events())

    def session_ids(self) -> set[str]:
        return {ev.session_id for ev in self.iter_events()}

    def distinct_sessions(self) -> int:
        return len(self.session_ids())

    def prune(
        self, *, days: int, now: datetime | None = None, apply: bool = False
    ) -> list[str]:
        """Delete event-day directories older than ``days`` (FR-CAP-6 raw-event TTL).

        Returns the day names pruned (in dry-run, the ones that WOULD be pruned).
        A ``YYYY-MM-DD`` day dir strictly before ``now - days`` is removed; today's
        dir and any non-date-named dir are kept. Callers default to dry-run because
        deletion is destructive (§8 SAFETY)."""
        if not self.events_dir.exists():
            return []
        cutoff = (now or utcnow()).date() - timedelta(days=days)
        pruned: list[str] = []
        for day in sorted(self.events_dir.iterdir()):
            if not day.is_dir():
                continue
            try:
                d = datetime.strptime(day.name, "%Y-%m-%d").date()
            except ValueError:
                continue  # not a date-named dir — never prune
            if d < cutoff:
                pruned.append(day.name)
                if apply:
                    shutil.rmtree(day)
        return pruned
