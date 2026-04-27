from __future__ import annotations

from tc_sniper.client import MoodleTcbClient
from tc_sniper.models import LoginFlowState, SessionStatus
from tc_sniper.session_store import SessionStore


class SessionService:
    def __init__(self, store: SessionStore, login_flow_getter) -> None:
        self.store = store
        self.login_flow_getter = login_flow_getter

    def get_status(self, revalidate: bool = False) -> SessionStatus:
        session = self.store.load()
        login_flow: LoginFlowState = self.login_flow_getter()
        if session is None:
            return SessionStatus(
                status="logged_out",
                message="Zadna ulozena session.",
                login_flow=login_flow,
            )

        status = SessionStatus(
            status="unknown",
            host=session.host,
            storage_state_path=str(session.storage_state_path),
            created_at=session.created_at,
            validated_at=session.validated_at,
            message="Session nalezena, bez revalidace.",
            login_flow=login_flow,
        )

        if revalidate:
            try:
                client = MoodleTcbClient(self.store)
                try:
                    valid = client.validate_session()
                finally:
                    client.close()
            except Exception as exc:
                status.status = "expired"
                status.message = f"Session validation failed: {exc}"
                return status

            status.status = "valid" if valid else "expired"
            status.message = "Session je platna." if valid else "Session vyprsela. Spust login znovu."
        return status

    def logout(self) -> SessionStatus:
        self.store.clear()
        return SessionStatus(status="logged_out", message="Lokalni session byla smazana.", login_flow=self.login_flow_getter())
