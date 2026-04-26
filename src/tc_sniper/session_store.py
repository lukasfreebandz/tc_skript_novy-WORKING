from __future__ import annotations

import json

from httpx import Cookies

from tc_sniper.models import SessionState
from tc_sniper.settings import STORAGE_STATE_PATH, clear_session_state, load_session_state, save_session_state, update_session_validation


class SessionStore:
    def load(self) -> SessionState | None:
        return load_session_state()

    def save(self, host: str) -> SessionState:
        return save_session_state(host)

    def clear(self) -> None:
        clear_session_state()

    def mark_validated(self) -> None:
        update_session_validation()

    def load_httpx_cookies(self) -> Cookies:
        raw = json.loads(STORAGE_STATE_PATH.read_text(encoding="utf-8"))
        cookies = Cookies()
        for cookie in raw.get("cookies", []):
            domain = cookie.get("domain") or ""
            cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=domain.lstrip("."),
                path=cookie.get("path", "/"),
            )
        return cookies

