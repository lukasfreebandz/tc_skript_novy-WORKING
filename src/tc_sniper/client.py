from __future__ import annotations

from dataclasses import dataclass

import httpx

from tc_sniper.models import AvailableSlot, Reservation, TcbCourse
from tc_sniper.parsing import parse_course_page, parse_sesskey, parse_slots, registration_succeeded
from tc_sniper.session_store import SessionStore


@dataclass
class BookingOutcome:
    ok: bool
    html: str
    reservation: Reservation | None
    message: str


class MoodleTcbClient:
    def __init__(self, store: SessionStore) -> None:
        session = store.load()
        if session is None:
            raise RuntimeError("Nenalezena session. Spust nejdriv 'tc-sniper login'.")
        self.store = store
        self.host = session.host
        self.cookies = store.load_httpx_cookies()
        self.http = httpx.Client(
            base_url=f"https://{self.host}",
            cookies=self.cookies,
            follow_redirects=True,
            headers={"User-Agent": "tc-sniper/0.3"},
            timeout=30.0,
        )

    def close(self) -> None:
        self.http.close()

    def validate_session(self) -> bool:
        response = self.http.get("/my/")
        html_text = response.text
        looks_logged_in = any(marker in html_text for marker in ("usertext", "/login/logout.php", "action-menu-toggle-0"))
        valid = response.status_code == 200 and "/login/index.php" not in str(response.url) and looks_logged_in
        if valid:
            self.store.mark_validated()
        return valid

    def fetch_course(self, tcb_url: str) -> TcbCourse:
        response = self.http.get(tcb_url)
        return parse_course_page(response.text, str(response.url))

    def fetch_slots(self, tcb_id: int, quiz_id: int, day: str) -> tuple[str, str, list[AvailableSlot]]:
        response = self.http.get(
            "/mod/tcb/view.php",
            params={"id": tcb_id, "quiz": quiz_id, "day": day},
        )
        html_text = response.text
        return html_text, parse_sesskey(html_text) or "", parse_slots(html_text)

    def register(self, tcb_id: int, quiz_id: int, slot_id: int, day: str, sesskey: str) -> BookingOutcome:
        response = self.http.post(
            "/mod/tcb/view.php",
            data={
                "id": tcb_id,
                "sesskey": sesskey,
                "tcbaction": "register",
                "quiz": quiz_id,
                "slot": slot_id,
                "day": day,
            },
        )
        course = parse_course_page(response.text, str(response.url))
        reservation = next((quiz.reservation for quiz in course.quizzes if quiz.quiz_id == quiz_id), None)
        ok = registration_succeeded(response.text) and reservation is not None
        return BookingOutcome(ok=ok, html=response.text, reservation=reservation, message="Reservation created." if ok else "Reservation failed.")

    def unregister(self, tcb_id: int, quiz_id: int, unregister_slot_id: int, day: str, sesskey: str) -> BookingOutcome:
        response = self.http.post(
            "/mod/tcb/view.php",
            data={
                "id": tcb_id,
                "sesskey": sesskey,
                "tcbaction": "unregister",
                "unregister": unregister_slot_id,
                "quiz": quiz_id,
                "day": day,
            },
        )
        course = parse_course_page(response.text, str(response.url))
        reservation = next((quiz.reservation for quiz in course.quizzes if quiz.quiz_id == quiz_id), None)
        ok = reservation is None
        return BookingOutcome(ok=ok, html=response.text, reservation=reservation, message="Reservation removed." if ok else "Unregister failed.")

    def change(self, tcb_id: int, quiz_id: int, old_slot_id: int, new_slot_id: int, day: str, sesskey: str) -> BookingOutcome:
        response = self.http.post(
            "/mod/tcb/view.php",
            data={
                "id": tcb_id,
                "sesskey": sesskey,
                "tcbaction": "change",
                "quiz": quiz_id,
                "slot": new_slot_id,
                "day": day,
                "changefrom": old_slot_id,
            },
        )
        course = parse_course_page(response.text, str(response.url))
        reservation = next((quiz.reservation for quiz in course.quizzes if quiz.quiz_id == quiz_id), None)
        ok = reservation is not None and reservation.unregister_slot_id != old_slot_id
        return BookingOutcome(ok=ok, html=response.text, reservation=reservation, message="Reservation changed." if ok else "Change failed.")
