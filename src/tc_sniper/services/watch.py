from __future__ import annotations

import queue
from collections import deque
from collections.abc import Callable
from datetime import date
from threading import Event, Lock, Thread

from tc_sniper.client import MoodleTcbClient
from tc_sniper.models import QuizOption, Reservation, WatchLogEvent, WatchPreferences, WatchResult, WatchRunState, WatchStartRequest
from tc_sniper.prompts import expand_days_input, parse_times_input
from tc_sniper.session_store import SessionStore
from tc_sniper.settings import append_event_log, utcnow


class WatchService:
    def __init__(self, store: SessionStore) -> None:
        self.store = store
        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._state = WatchRunState(status="idle", message="Watcher neni spusten.", active=False, updated_at=utcnow())
        self._subscribers: list[queue.Queue[WatchLogEvent]] = []
        self._recent_logs: deque[WatchLogEvent] = deque(maxlen=200)

    def prepare_preferences(self, request: WatchStartRequest) -> WatchPreferences:
        days = expand_days_input(request.days_raw)
        if not days:
            raise ValueError("Musis zadat aspon jeden den nebo rozsah.")

        if request.time_mode == "window":
            if request.window_start is None or request.window_end is None or request.window_step_minutes is None:
                raise ValueError("Window mod potrebuje cas OD, cas DO a krok v minutach.")
            times = parse_times_input("window", request.window_start, request.window_end, request.window_step_minutes)
        else:
            if not request.times_raw:
                raise ValueError("List mod potrebuje seznam casu.")
            times = parse_times_input("list", request.times_raw)

        if not times:
            raise ValueError("Musis zadat aspon jeden cas.")

        return WatchPreferences(
            tcb_url=request.tcb_url,
            quiz_id=request.quiz_id,
            quiz_title=request.quiz_title,
            days=days,
            times=times,
            poll_interval_seconds=request.poll_interval_seconds,
        )

    def validate_days_for_quiz(self, preferences: WatchPreferences, quiz: QuizOption) -> None:
        if not quiz.open_from_date or not quiz.open_to_date:
            return
        min_day = date.fromisoformat(quiz.open_from_date)
        max_day = date.fromisoformat(quiz.open_to_date)
        invalid_days = [day for day in preferences.days if date.fromisoformat(day) < min_day or date.fromisoformat(day) > max_day]
        if invalid_days:
            raise ValueError(
                "Vybrane dny jsou mimo povolene okno testu "
                f"({quiz.open_from_date} az {quiz.open_to_date}): {', '.join(invalid_days)}"
            )

    def prepare_preferences_with_course_validation(self, request: WatchStartRequest) -> WatchPreferences:
        preferences = self.prepare_preferences(request)
        client = MoodleTcbClient(self.store)
        try:
            if not client.validate_session():
                raise RuntimeError("Session vyprsela. Spust login znovu.")
            course = client.fetch_course(preferences.tcb_url)
        finally:
            client.close()
        quiz = next((item for item in course.quizzes if item.quiz_id == preferences.quiz_id), None)
        if quiz is None:
            raise ValueError("Vybrany test uz na TCB strance neni.")
        self.validate_days_for_quiz(preferences, quiz)
        return preferences

    def get_state(self) -> WatchRunState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def subscribe(self) -> tuple[queue.Queue[WatchLogEvent], Callable[[], None]]:
        q: queue.Queue[WatchLogEvent] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            current_logs = list(self._recent_logs)
        for item in current_logs:
            q.put(item)

        def unsubscribe() -> None:
            with self._lock:
                if q in self._subscribers:
                    self._subscribers.remove(q)

        return q, unsubscribe

    def _emit(self, event: WatchLogEvent) -> None:
        with self._lock:
            self._recent_logs.append(event)
            self._state.recent_logs = list(self._recent_logs)
            self._state.updated_at = utcnow()
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(event)

    def _set_state(self, status: str, message: str, *, active: bool, attempt: int | None = None, reservation: Reservation | None = None, preferences: WatchPreferences | None = None) -> None:
        with self._lock:
            self._state = WatchRunState(
                status=status,  # type: ignore[arg-type]
                message=message,
                active=active,
                attempt=self._state.attempt if attempt is None else attempt,
                started_at=self._state.started_at if active else (self._state.started_at if status == "booked" else None),
                updated_at=utcnow(),
                preferences=preferences if preferences is not None else self._state.preferences,
                reservation=reservation,
                recent_logs=list(self._recent_logs),
            )
            current = self._state.model_copy(deep=True)
        self._emit(WatchLogEvent(timestamp=current.updated_at, level="state", message=message, attempt=current.attempt, state=current.status))

    def run_blocking(self, preferences: WatchPreferences, on_log: Callable[[WatchLogEvent], None], stop_event: Event | None = None) -> WatchResult:
        local_stop = stop_event or Event()
        client = MoodleTcbClient(self.store)
        try:
            self._set_state("validating_session", "Overuji session pred startem watcheru.", active=True, attempt=0, preferences=preferences)
            if not client.validate_session():
                self._set_state("error", "Session vyprsela. Spust login znovu.", active=False, preferences=preferences)
                return WatchResult(status="error", message="Session vyprsela. Spust login znovu.")

            attempt = 0
            while not local_stop.is_set():
                attempt += 1
                self._set_state("discovering_course", f"Obnovuji TCB stranku, pruchod #{attempt}.", active=True, attempt=attempt, preferences=preferences)
                course = client.fetch_course(preferences.tcb_url)
                quiz = next((item for item in course.quizzes if item.quiz_id == preferences.quiz_id), None)
                if quiz is None:
                    self._set_state("error", "Vybrany test uz na TCB strance neni.", active=False, attempt=attempt, preferences=preferences)
                    return WatchResult(status="error", message="Vybrany test uz na TCB strance neni.")
                try:
                    self.validate_days_for_quiz(preferences, quiz)
                except ValueError as exc:
                    self._set_state("error", str(exc), active=False, attempt=attempt, preferences=preferences)
                    return WatchResult(status="error", message=str(exc))
                if quiz.reservation is not None:
                    self._set_state("already_reserved", "Pro tento test uz existuje rezervace.", active=False, attempt=attempt, reservation=quiz.reservation, preferences=preferences)
                    return WatchResult(status="already_reserved", message="Pro tento test uz existuje rezervace.", reservation=quiz.reservation)

                self._set_state("running", f"Pruchod #{attempt}: kontroluji dny a casy.", active=True, attempt=attempt, preferences=preferences)
                available_days = {day.date for day in quiz.available_days}
                for day in preferences.days:
                    if local_stop.is_set():
                        break
                    if day not in available_days:
                        event = WatchLogEvent(
                            timestamp=utcnow(),
                            level="info",
                            message=f"{day}: den neni dostupny",
                            attempt=attempt,
                            day=day,
                            state="running",
                        )
                        self._emit(event)
                        on_log(event)
                        continue

                    event = WatchLogEvent(
                        timestamp=utcnow(),
                        level="info",
                        message=f"{day}: zkousim casy {', '.join(preferences.times)}",
                        attempt=attempt,
                        day=day,
                        state="running",
                    )
                    self._emit(event)
                    on_log(event)
                    _, sesskey, slots = client.fetch_slots(course.tcb_id, preferences.quiz_id, day)
                    slot_map = {slot.time: slot for slot in slots}
                    matching = [slot_map[label] for label in preferences.times if label in slot_map]
                    if not matching:
                        miss = WatchLogEvent(
                            timestamp=utcnow(),
                            level="warning",
                            message=f"{day}: zadny z preferovanych casu neni volny",
                            attempt=attempt,
                            day=day,
                            state="running",
                        )
                        self._emit(miss)
                        on_log(miss)
                        continue

                    target = matching[0]
                    self._set_state(
                        "attempting_booking",
                        f"Rezervuji slot {target.day} {target.time}.",
                        active=True,
                        attempt=attempt,
                        preferences=preferences,
                    )
                    found = WatchLogEvent(
                        timestamp=utcnow(),
                        level="success",
                        message=f"Nalezen matching slot {target.day} {target.time} ({target.seats} mist). Rezervuji...",
                        attempt=attempt,
                        day=target.day,
                        time=target.time,
                        seats=target.seats,
                        state="attempting_booking",
                    )
                    self._emit(found)
                    on_log(found)
                    outcome = client.register(course.tcb_id, preferences.quiz_id, target.slot_id, target.day, sesskey)
                    if outcome.ok and outcome.reservation is not None:
                        append_event_log(
                            f"BOOKED quiz={preferences.quiz_id} day={outcome.reservation.day} time={outcome.reservation.time}"
                        )
                        self._set_state(
                            "booked",
                            f"Rezervace potvrzena pro {outcome.reservation.day} {outcome.reservation.time}.",
                            active=False,
                            attempt=attempt,
                            reservation=outcome.reservation,
                            preferences=preferences,
                        )
                        return WatchResult(status="booked", message="Reservation created.", reservation=outcome.reservation)

                    failed = WatchLogEvent(
                        timestamp=utcnow(),
                        level="error",
                        message="Rezervace se nepodarila, watcher pokracuje.",
                        attempt=attempt,
                        day=target.day,
                        time=target.time,
                        state="running",
                    )
                    self._emit(failed)
                    on_log(failed)
                    self._set_state("running", "Rezervace se nepodarila, watcher pokracuje.", active=True, attempt=attempt, preferences=preferences)

                if local_stop.wait(preferences.poll_interval_seconds):
                    break

            self._set_state("stopped", "Watcher byl zastaven.", active=False, attempt=self._state.attempt, preferences=preferences)
            return WatchResult(status="stopped", message="Watcher byl zastaven.")
        finally:
            client.close()

    def start(self, request: WatchStartRequest) -> WatchRunState:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Watcher uz bezi. Nejdriv ho zastav.")
            self._stop_event = Event()
            preferences = self.prepare_preferences_with_course_validation(request)
            self._state = WatchRunState(
                status="validating_session",
                message="Spoustim watcher.",
                active=True,
                attempt=0,
                started_at=utcnow(),
                updated_at=utcnow(),
                preferences=preferences,
                recent_logs=list(self._recent_logs),
            )
            self._thread = Thread(target=self._run_async, args=(preferences,), daemon=True)
            self._thread.start()
            return self._state.model_copy(deep=True)

    def _run_async(self, preferences: WatchPreferences) -> None:
        self.run_blocking(preferences, on_log=lambda _: None, stop_event=self._stop_event)

    def stop(self) -> WatchRunState:
        self._stop_event.set()
        return self.get_state()
