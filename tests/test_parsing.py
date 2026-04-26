from pathlib import Path

from tc_sniper.parsing import parse_course_page, parse_slots, parse_sesskey, parse_tcb_url, registration_succeeded


FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_tcb_url() -> None:
    host, tcb_id = parse_tcb_url("https://moodle.czu.cz/mod/tcb/view.php?id=897230")
    assert host == "moodle.czu.cz"
    assert tcb_id == 897230


def test_parse_course_page_finds_quizzes_and_days() -> None:
    course = parse_course_page(
        read_fixture("tcb_course.html"),
        "https://moodle.czu.cz/mod/tcb/view.php?id=897230",
    )
    assert course.sesskey == "ABC123"
    assert len(course.quizzes) == 2
    assert course.quizzes[1].quiz_id == 825698
    assert [day.date for day in course.quizzes[1].available_days] == ["2026-05-02", "2026-05-03"]


def test_parse_slots_reads_register_actions() -> None:
    slots = parse_slots(read_fixture("tcb_slots.html"))
    assert [slot.time for slot in slots] == ["08:40", "14:30"]
    assert slots[1].slot_id == 474530
    assert slots[1].seats == 5
    assert slots[1].action == "register"


def test_parse_reserved_state_and_change_actions() -> None:
    course = parse_course_page(
        read_fixture("tcb_reserved_change.html"),
        "https://moodle.czu.cz/mod/tcb/view.php?id=897230",
    )
    reservation = course.quizzes[0].reservation
    assert reservation is not None
    assert reservation.unregister_slot_id == 474165
    slots = parse_slots(read_fixture("tcb_reserved_change.html"))
    assert slots[0].action == "change"
    assert slots[0].changefrom == 474165


def test_registration_success_parser() -> None:
    html_text = read_fixture("tcb_success.html")
    assert parse_sesskey(html_text) == "XYZ987"
    assert registration_succeeded(html_text) is True
    course = parse_course_page(
        html_text,
        "https://moodle.czu.cz/mod/tcb/view.php?id=897230&quiz=825698&day=2026-05-02",
    )
    assert course.quizzes[0].reservation is not None
    assert course.quizzes[0].reservation.time == "08:40"

