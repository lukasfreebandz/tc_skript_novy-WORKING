from __future__ import annotations

from datetime import datetime
from pathlib import Path

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

