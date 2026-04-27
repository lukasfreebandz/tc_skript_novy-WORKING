from __future__ import annotations

from tc_sniper.client import MoodleTcbClient
from tc_sniper.models import TcbCourse
from tc_sniper.parsing import parse_tcb_url
from tc_sniper.session_store import SessionStore


class CourseService:
    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def discover(self, tcb_url: str) -> TcbCourse:
        parse_tcb_url(tcb_url)
        client = MoodleTcbClient(self.store)
        try:
            if not client.validate_session():
                raise RuntimeError("Session vyprsela. Spust login znovu.")
            return client.fetch_course(tcb_url)
        finally:
            client.close()
