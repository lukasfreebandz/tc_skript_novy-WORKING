from __future__ import annotations

from tc_sniper.services.auth import LoginFlowService
from tc_sniper.services.courses import CourseService
from tc_sniper.services.session import SessionService
from tc_sniper.services.watch import WatchService
from tc_sniper.session_store import SessionStore


class AppServices:
    def __init__(self) -> None:
        self.store = SessionStore()
        self.login_flow = LoginFlowService(self.store)
        self.session = SessionService(self.store, self.login_flow.get_state)
        self.courses = CourseService(self.store)
        self.watch = WatchService(self.store)
