from __future__ import annotations

from pathlib import Path

from tc_sniper.models import QuizOption, WatchPreferences, WatchStartRequest
from tc_sniper.services.watch import WatchService
from tc_sniper.session_store import SessionStore
from tc_sniper.settings import read_recent_event_items


def test_watch_service_prepares_list_mode_preferences() -> None:
    service = WatchService(SessionStore())
    preferences = service.prepare_preferences(
        WatchStartRequest(
            tcb_url="https://moodle.czu.cz/mod/tcb/view.php?id=897230",
            quiz_id=825698,
            quiz_title="OSA - Zapoctovy test 2",
            day_mode="range",
            days_raw="2026-05-30..2026-06-01",
            time_mode="list",
            times_raw="08:40,14:30",
            poll_interval_seconds=5,
        )
    )
    assert preferences.days == ["2026-05-30", "2026-05-31", "2026-06-01"]
    assert preferences.times == ["08:40", "14:30"]
    assert preferences.poll_interval_seconds == 5


def test_watch_service_prepares_window_mode_preferences() -> None:
    service = WatchService(SessionStore())
    preferences = service.prepare_preferences(
        WatchStartRequest(
            tcb_url="https://moodle.czu.cz/mod/tcb/view.php?id=897230",
            quiz_id=825698,
            quiz_title="OSA - Zapoctovy test 2",
            day_mode="list",
            days_raw="2026-05-30",
            time_mode="window",
            window_start="08:00",
            window_end="08:20",
            window_step_minutes=10,
        )
    )
    assert preferences.times == ["08:00", "08:10", "08:20"]


def test_watch_service_rejects_days_outside_quiz_window() -> None:
    service = WatchService(SessionStore())
    preferences = WatchPreferences(
        tcb_url="https://moodle.czu.cz/mod/tcb/view.php?id=897230",
        quiz_id=825698,
        quiz_title="OSA - Zapoctovy test 2",
        days=["2026-05-30"],
        times=["08:20"],
    )
    quiz = QuizOption(
        quiz_id=825698,
        title="OSA - Zapoctovy test 2",
        quiz_url="https://moodle.czu.cz/mod/quiz/view.php?id=825698",
        open_from_date="2026-04-13",
        open_to_date="2026-05-29",
    )
    try:
        service.validate_days_for_quiz(preferences, quiz)
        assert False, "Expected ValueError for day outside quiz window"
    except ValueError as exc:
        assert "2026-05-30" in str(exc)


def test_read_recent_event_items_parses_booked_log(monkeypatch) -> None:
    log_path = Path("tests/.tmp-events.log")
    log_path.write_text("2026-04-26T12:00:00+00:00 BOOKED quiz=825698 day=2026-05-02 time=08:20\n", encoding="utf-8")
    try:
        monkeypatch.setattr("tc_sniper.settings.EVENT_LOG_PATH", log_path)
        items = read_recent_event_items()
        assert len(items) == 1
        assert items[0].action == "BOOKED"
        assert items[0].quiz_id == 825698
        assert items[0].day == "2026-05-02"
        assert items[0].time == "08:20"
    finally:
        if log_path.exists():
            log_path.unlink()
