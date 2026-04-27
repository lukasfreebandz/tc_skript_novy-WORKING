from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tc_sniper.models import RecentEventItem, SessionState


APP_DIR = Path.home() / ".tc-sniper"
SESSION_DIR = APP_DIR / "session"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"
SESSION_META_PATH = SESSION_DIR / "session_meta.json"
EVENT_LOG_PATH = APP_DIR / "events.log"

EVENT_LINE_RE = re.compile(
    r"^(?P<ts>\S+)\s+(?P<action>[A-Z_]+)(?:\s+quiz=(?P<quiz_id>\d+))?(?:\s+day=(?P<day>\d{4}-\d{2}-\d{2}))?(?:\s+time=(?P<time>\d{2}:\d{2}))?$"
)


def ensure_app_dirs() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def load_session_state() -> SessionState | None:
    if not STORAGE_STATE_PATH.exists() or not SESSION_META_PATH.exists():
        return None
    meta = read_json(SESSION_META_PATH)
    return SessionState(
        host=meta["host"],
        storage_state_path=STORAGE_STATE_PATH,
        created_at=datetime.fromisoformat(meta["created_at"]),
        validated_at=datetime.fromisoformat(meta["validated_at"]) if meta.get("validated_at") else None,
    )


def save_session_state(host: str) -> SessionState:
    ensure_app_dirs()
    now = utcnow()
    meta = {
        "host": host,
        "created_at": now.isoformat(),
        "validated_at": now.isoformat(),
    }
    write_json(SESSION_META_PATH, meta)
    return SessionState(
        host=host,
        storage_state_path=STORAGE_STATE_PATH,
        created_at=now,
        validated_at=now,
    )


def update_session_validation() -> None:
    if not SESSION_META_PATH.exists():
        return
    meta = read_json(SESSION_META_PATH)
    meta["validated_at"] = utcnow().isoformat()
    write_json(SESSION_META_PATH, meta)


def clear_session_state() -> None:
    for path in (STORAGE_STATE_PATH, SESSION_META_PATH):
        if path.exists():
            path.unlink()


def append_event_log(line: str) -> None:
    ensure_app_dirs()
    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{utcnow().isoformat()} {line}\n")


def read_recent_event_items(limit: int = 20) -> list[RecentEventItem]:
    if not EVENT_LOG_PATH.exists():
        return []

    events: list[RecentEventItem] = []
    for raw_line in EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = EVENT_LINE_RE.match(line)
        if not match:
            continue
        events.append(
            RecentEventItem(
                timestamp=datetime.fromisoformat(match.group("ts")),
                action=match.group("action"),
                quiz_id=int(match.group("quiz_id")) if match.group("quiz_id") else None,
                day=match.group("day"),
                time=match.group("time"),
            )
        )
    return list(reversed(events[-limit:]))
