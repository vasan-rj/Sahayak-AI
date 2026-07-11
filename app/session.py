"""Session — the object the relay, reconnect, and per-session witness log hang off.

Every connection gets a Session with:
- a unique id,
- its own witness log file,
- a bounded outbound queue drained by exactly ONE writer task (so concurrent
  producers — echo now; audio-out + caption + event later — never race on the
  socket),
- a reserved ``resume_handle`` for the Gemini session-resumption token (not
  implemented today; reserving the field now is a one-line add that is painful
  to thread in later).

Outbound backpressure policy (decided now, enforced later): the queue is bounded.
UI/media-derived messages are droppable under pressure; witness-log-relevant
events are not. Today nothing stresses it — the bound + policy note exist so this
is a resize, not a redesign, when media lands.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from typing import Any

from .form_state import FormState
from .witness_log import WitnessLog

OUTBOUND_MAXSIZE = 100


def _default_log_dir() -> str:
    # Logs live OUTSIDE the reload-watched package tree. If uvicorn --reload
    # watched these, every append would trigger a restart and drop live sessions.
    return os.environ.get("SAHAYAK_LOG_DIR", os.path.join(os.getcwd(), "data", "witness"))


@dataclass
class Session:
    id: str
    log: WitnessLog
    outbound: "asyncio.Queue[dict]"
    form: FormState
    ws: Any = None  # live WebSocket, attached by the /ws handler after accept
    relay: Any = None  # LiveRelay to the Gemini Live session, attached by /ws
    resume_handle: str | None = None  # reserved: Gemini session-resumption token
    state: str = "open"


class SessionRegistry:
    def __init__(self, log_dir: str | None = None):
        self.log_dir = log_dir or _default_log_dir()
        os.makedirs(self.log_dir, exist_ok=True)
        self._sessions: dict[str, Session] = {}

    def create(self, template: dict | None = None) -> Session:
        sid = uuid.uuid4().hex
        log = WitnessLog(os.path.join(self.log_dir, f"{sid}.jsonl"))
        session = Session(
            id=sid,
            log=log,
            outbound=asyncio.Queue(maxsize=OUTBOUND_MAXSIZE),
            form=FormState(template),
        )
        self._sessions[sid] = session
        return session

    def get(self, sid: str) -> Session | None:
        return self._sessions.get(sid)

    def remove(self, sid: str) -> None:
        self._sessions.pop(sid, None)

    def __len__(self) -> int:
        return len(self._sessions)
