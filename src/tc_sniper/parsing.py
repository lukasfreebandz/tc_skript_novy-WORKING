from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlparse

from tc_sniper.models import AvailableDay, AvailableSlot, QuizOption, Reservation, TcbCourse


QUIZ_SECTION_RE = re.compile(
    r"<h3>Test:\s*<a href=\"(?P<href>[^\"]*?/mod/quiz/view\.php\?id=(?P<quiz_id>\d+)[^\"]*)\">(?P<title>.*?)</a></h3>(?P<body>.*?)(?=(?:<hr><h3>Test:)|(?:<div><hr></div>)|(?:<div id=\"adaptable-activity-navigation\">)|\Z)",
    re.S,
)

DAY_LINK_RE = re.compile(
    r"<td class=\"alert alert-success[^\"]*\">.*?<a href=\"(?P<href>[^\"]*?\?id=\d+&(?:amp;)?day=(?P<day>\d{4}-\d{2}-\d{2})&(?:amp;)?quiz=(?P<quiz_id>\d+)[^\"]*)\">.*?\((?P<seats>\d+)[^)]*\)</a>.*?</td>",
    re.S,
)

SLOT_CELL_RE = re.compile(
    r"<td class=\"alert alert-success[^\"]*\">.*?<form[^>]*>(?P<form>.*?)</form></strong>\s*\((?P<seats>\d+)[^)]*\)</td>",
    re.S,
)

INPUT_RE = re.compile(r"<input[^>]*name=\"(?P<name>[^\"]+)\"[^>]*value=\"(?P<value>[^\"]*)\"[^>]*>", re.S)
BUTTON_RE = re.compile(r"<button[^>]*>(?P<label>.*?)</button>", re.S)
SESSKEY_RE = re.compile(r"\"sesskey\":\"([^\"]+)\"")
COURSE_TITLE_RE = re.compile(r"<span id=\"coursetitle\">(.*?)</span>", re.S)
SUCCESS_REGISTER_RE = re.compile(r"registroval\(a\).*?Testovac", re.I | re.S)
RESERVATION_ROW_RE = re.compile(
    r"<tr><td>Rezervovan.*?term.*?:</td><td>(?P<date>\d{2}\.\d{2}\.\d{4})</td><td>(?P<time>\d{2}:\d{2})</td><td>(?P<arrive>[^<]*)</td><td>.*?<input type=\"hidden\" name=\"tcbaction\" value=\"unregister\">.*?<input type=\"hidden\" name=\"unregister\" value=\"(?P<unregister>\d+)\">.*?<input type=\"hidden\" name=\"quiz\" value=\"(?P<quiz_id>\d+)\">.*?<input type=\"hidden\" name=\"day\" value=\"(?P<day>\d{4}-\d{2}-\d{2})\">.*?</form></strong>\s*\((?P<deadline>[^)]*)\)",
    re.I | re.S,
)
INFO_ROW_RE = re.compile(r"<tr[^>]*>\s*<td[^>]*>(?P<label>.*?)</td>\s*<td[^>]*>(?P<value>.*?)</td>\s*</tr>", re.I | re.S)


def _strip_tags(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", "", value)
    return html.unescape(" ".join(no_tags.split()))


def _parse_hidden_inputs(fragment: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in INPUT_RE.finditer(fragment):
        result[match.group("name")] = html.unescape(match.group("value"))
    return result


def parse_tcb_url(tcb_url: str) -> tuple[str, int]:
    parsed = urlparse(tcb_url)
    if parsed.scheme != "https" or parsed.hostname != "moodle.czu.cz" or parsed.path != "/mod/tcb/view.php":
        raise ValueError("URL musi byt platna TCB stranka na hostu moodle.czu.cz (/mod/tcb/view.php).")
    query = parse_qs(parsed.query)
    if "id" not in query:
        raise ValueError("TCB URL musi obsahovat parametr id=...")
    return parsed.hostname, int(query["id"][0])


def parse_sesskey(html_text: str) -> str | None:
    match = SESSKEY_RE.search(html_text)
    return match.group(1) if match else None


def parse_course_page(html_text: str, source_url: str) -> TcbCourse:
    host, tcb_id = parse_tcb_url(source_url)
    title_match = COURSE_TITLE_RE.search(html_text)
    course = TcbCourse(
        host=host,
        tcb_id=tcb_id,
        course_title=_strip_tags(title_match.group(1)) if title_match else None,
        sesskey=parse_sesskey(html_text),
        quizzes=[],
    )

    for match in QUIZ_SECTION_RE.finditer(html_text):
        quiz_id = int(match.group("quiz_id"))
        body = match.group("body")
        quiz_meta = parse_quiz_info_table(body)
        open_from = quiz_meta.get("otevřen od")
        open_to = quiz_meta.get("otevřen do")
        quiz = QuizOption(
            quiz_id=quiz_id,
            title=_strip_tags(match.group("title")),
            quiz_url=html.unescape(match.group("href")),
            open_from=open_from,
            open_to=open_to,
            open_from_date=_parse_cz_datetime_to_date(open_from),
            open_to_date=_parse_cz_datetime_to_date(open_to),
            duration=quiz_meta.get("doba trvání"),
            available_days=parse_available_days(body, source_url),
            reservation=parse_reservation(body),
        )
        course.quizzes.append(quiz)

    return course


def parse_available_days(html_fragment: str, source_url: str) -> list[AvailableDay]:
    days: list[AvailableDay] = []
    for match in DAY_LINK_RE.finditer(html_fragment):
        href = html.unescape(match.group("href")).replace("&amp;", "&")
        days.append(
            AvailableDay(
                date=match.group("day"),
                seats=int(match.group("seats")),
                url=urljoin(source_url, href),
            )
        )
    deduped: dict[str, AvailableDay] = {}
    for day in days:
        deduped[day.date] = day
    return list(deduped.values())


def parse_quiz_info_table(html_fragment: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    label_map = {
        "otevren od": "otevřen od",
        "otevren do": "otevřen do",
        "doba trvani": "doba trvání",
    }
    for row_match in INFO_ROW_RE.finditer(html_fragment):
        raw_label = _strip_tags(row_match.group("label")).strip()
        raw_value = _strip_tags(row_match.group("value")).strip()
        normalized = _normalize_label(raw_label)
        if normalized in label_map and raw_value:
            rows[label_map[normalized]] = raw_value
    return rows


def _normalize_label(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_value.lower().split())


def _parse_cz_datetime_to_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y %H:%M").date().isoformat()
    except ValueError:
        return None


def parse_reservation(html_fragment: str) -> Reservation | None:
    match = RESERVATION_ROW_RE.search(html_fragment)
    if not match:
        return None
    arrive = _strip_tags(match.group("arrive")).strip() or None
    deadline = _strip_tags(match.group("deadline")).strip() or None
    return Reservation(
        quiz_id=int(match.group("quiz_id")),
        day=match.group("day"),
        time=match.group("time"),
        arrive_at=arrive,
        unregister_slot_id=int(match.group("unregister")),
        unregister_deadline=deadline,
    )


def parse_slots(html_text: str) -> list[AvailableSlot]:
    slots: list[AvailableSlot] = []
    for match in SLOT_CELL_RE.finditer(html_text):
        form = match.group("form")
        values = _parse_hidden_inputs(form)
        button = BUTTON_RE.search(form)
        if not button or "slot" not in values or "quiz" not in values or "day" not in values:
            continue
        label = _strip_tags(button.group("label"))
        time = label.split(" - ", 1)[0].strip()
        slots.append(
            AvailableSlot(
                slot_id=int(values["slot"]),
                day=values["day"],
                quiz_id=int(values["quiz"]),
                time=time,
                seats=int(match.group("seats")),
                action=values.get("tcbaction", "register"),
                changefrom=int(values["changefrom"]) if values.get("changefrom") else None,
            )
        )
    return slots


def registration_succeeded(html_text: str) -> bool:
    return bool(SUCCESS_REGISTER_RE.search(html_text))
