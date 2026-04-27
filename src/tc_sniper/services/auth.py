from __future__ import annotations

from datetime import datetime
from threading import Event, Lock, Thread

from tc_sniper.auth import run_login_flow
from tc_sniper.models import LoginFlowState
from tc_sniper.session_store import SessionStore
from tc_sniper.settings import utcnow


class LoginFlowService:
    def __init__(self, store: SessionStore) -> None:
        self.store = store
        self._lock = Lock()
        self._confirm_event: Event | None = None
        self._thread: Thread | None = None
        self._state = LoginFlowState(status="idle", message="Login neni aktivni.")

    def get_state(self) -> LoginFlowState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def _set_state(
        self,
        status: str,
        *,
        host: str | None = None,
        message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        with self._lock:
            self._state = LoginFlowState(
                status=status,  # type: ignore[arg-type]
                host=host or self._state.host,
                message=message,
                started_at=started_at if started_at is not None else self._state.started_at,
                finished_at=finished_at,
            )

    def start(self, host: str = "moodle.czu.cz") -> LoginFlowState:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Login uz probiha.")
            self._confirm_event = Event()
            started_at = utcnow()
            self._state = LoginFlowState(
                status="opening_browser",
                host=host,
                message="Oteviram browser pro prihlaseni.",
                started_at=started_at,
            )
            self._thread = Thread(target=self._run_login, args=(host, started_at), daemon=True)
            self._thread.start()
            return self._state.model_copy(deep=True)

    def confirm(self) -> LoginFlowState:
        with self._lock:
            if self._confirm_event is None or self._thread is None or not self._thread.is_alive():
                raise RuntimeError("Neni co potvrdit, login momentalne nebezi.")
            self._state = LoginFlowState(
                status="completing",
                host=self._state.host,
                message="Dokoncuji overeni prihlaseni.",
                started_at=self._state.started_at,
            )
            self._confirm_event.set()
            return self._state.model_copy(deep=True)

    def _run_login(self, host: str, started_at: datetime) -> None:
        try:
            run_login_flow(
                host=host,
                store=self.store,
                wait_for_confirmation=lambda: self._confirm_event.wait() if self._confirm_event is not None else None,
                on_browser_opened=lambda: self._set_state(
                    "waiting_for_confirmation",
                    host=host,
                    message="Prihlas se v browseru a pak klikni na Potvrdit.",
                    started_at=started_at,
                ),
                on_completing=lambda: self._set_state(
                    "completing",
                    host=host,
                    message="Overuji prihlasenou session.",
                    started_at=started_at,
                ),
            )
        except Exception as exc:
            self._set_state(
                "error",
                host=host,
                message=str(exc),
                started_at=started_at,
                finished_at=utcnow(),
            )
        else:
            self._set_state(
                "success",
                host=host,
                message="Session byla uspesne ulozena.",
                started_at=started_at,
                finished_at=utcnow(),
            )
