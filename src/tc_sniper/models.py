from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SessionState(BaseModel):
    host: str
    storage_state_path: Path
    created_at: datetime
    validated_at: datetime | None = None


class AvailableDay(BaseModel):
    date: str
    seats: int
    url: str


class AvailableSlot(BaseModel):
    slot_id: int
    day: str
    quiz_id: int
    time: str
    seats: int
    action: str = "register"
    changefrom: int | None = None


class Reservation(BaseModel):
    quiz_id: int
    day: str
    time: str
    arrive_at: str | None = None
    unregister_slot_id: int | None = None
    unregister_deadline: str | None = None


class QuizOption(BaseModel):
    quiz_id: int
    title: str
    quiz_url: str
    open_from: str | None = None
    open_to: str | None = None
    open_from_date: str | None = None
    open_to_date: str | None = None
    duration: str | None = None
    available_days: list[AvailableDay] = Field(default_factory=list)
    reservation: Reservation | None = None


class TcbCourse(BaseModel):
    host: str
    tcb_id: int
    course_title: str | None = None
    sesskey: str | None = None
    quizzes: list[QuizOption] = Field(default_factory=list)


class WatchPreferences(BaseModel):
    tcb_url: str
    quiz_id: int
    quiz_title: str
    days: list[str]
    times: list[str]
    poll_interval_seconds: int = 10


class WatchResult(BaseModel):
    status: str
    message: str
    reservation: Reservation | None = None


class LoginStartRequest(BaseModel):
    host: str = "moodle.czu.cz"


class LoginFlowState(BaseModel):
    status: Literal["idle", "opening_browser", "waiting_for_confirmation", "completing", "success", "error"]
    host: str | None = None
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SessionStatus(BaseModel):
    status: Literal["logged_out", "valid", "expired", "unknown"]
    host: str | None = None
    storage_state_path: str | None = None
    created_at: datetime | None = None
    validated_at: datetime | None = None
    message: str | None = None
    login_flow: LoginFlowState | None = None


class DiscoverCourseRequest(BaseModel):
    tcb_url: str


class WatchStartRequest(BaseModel):
    tcb_url: str
    quiz_id: int
    quiz_title: str
    day_mode: Literal["list", "range"] = "list"
    days_raw: str
    time_mode: Literal["list", "window"] = "list"
    times_raw: str | None = None
    window_start: str | None = None
    window_end: str | None = None
    window_step_minutes: int | None = None
    poll_interval_seconds: int = 10


class WatchLogEvent(BaseModel):
    timestamp: datetime
    level: Literal["info", "success", "warning", "error", "state"]
    message: str
    attempt: int | None = None
    day: str | None = None
    time: str | None = None
    seats: int | None = None
    state: str | None = None


class WatchRunState(BaseModel):
    status: Literal[
        "idle",
        "validating_session",
        "discovering_course",
        "running",
        "attempting_booking",
        "booked",
        "already_reserved",
        "stopped",
        "error",
    ]
    message: str
    active: bool = False
    attempt: int = 0
    started_at: datetime | None = None
    updated_at: datetime
    preferences: WatchPreferences | None = None
    reservation: Reservation | None = None
    recent_logs: list[WatchLogEvent] = Field(default_factory=list)


class RecentEventItem(BaseModel):
    timestamp: datetime
    action: str
    quiz_id: int | None = None
    day: str | None = None
    time: str | None = None
