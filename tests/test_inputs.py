from datetime import date

from tc_sniper.prompts import (
    compute_effective_day_bounds,
    build_times_from_window,
    expand_days_input,
    parse_human_date,
    parse_quiz_open_date,
    parse_times_input,
    validate_days_within_bounds,
)


def test_expand_days_range() -> None:
    assert expand_days_input("2026-05-02..2026-05-04") == ["2026-05-02", "2026-05-03", "2026-05-04"]


def test_expand_days_list() -> None:
    assert expand_days_input("2026-05-02,2026-05-04") == ["2026-05-02", "2026-05-04"]


def test_parse_human_date_rejects_non_iso_format() -> None:
    try:
        parse_human_date("30.05.2026")
    except ValueError as exc:
        assert "YYYY-MM-DD" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-ISO date format.")


def test_build_times_from_window() -> None:
    assert build_times_from_window("14:20", "14:50", 10) == ["14:20", "14:30", "14:40", "14:50"]


def test_parse_times_list_mode() -> None:
    assert parse_times_input("list", "08:40,14:30") == ["08:40", "14:30"]


def test_parse_quiz_open_date() -> None:
    assert parse_quiz_open_date("13.04.2026 08:00") == date(2026, 4, 13)


def test_validate_days_within_bounds_accepts_allowed_days() -> None:
    validate_days_within_bounds(
        ["2026-04-13", "2026-04-20"],
        min_day=date(2026, 4, 13),
        max_day=date(2026, 5, 29),
    )


def test_validate_days_within_bounds_rejects_day_before_opening() -> None:
    try:
        validate_days_within_bounds(
            ["2026-04-12"],
            min_day=date(2026, 4, 13),
            max_day=date(2026, 5, 29),
        )
    except ValueError as exc:
        assert "2026-04-13" in str(exc)
    else:
        raise AssertionError("Expected ValueError for day before opening.")


def test_validate_days_within_bounds_rejects_day_after_closing() -> None:
    try:
        validate_days_within_bounds(
            ["2026-05-30"],
            min_day=date(2026, 4, 13),
            max_day=date(2026, 5, 29),
        )
    except ValueError as exc:
        assert "2026-05-29" in str(exc)
    else:
        raise AssertionError("Expected ValueError for day after closing.")


def test_effective_min_day_can_be_today_when_later_than_opening() -> None:
    today = date(2026, 4, 27)
    opening = date(2026, 4, 13)
    assert max(today, opening) == date(2026, 4, 27)


def test_compute_effective_day_bounds_uses_today_when_test_opened_earlier() -> None:
    min_day, max_day = compute_effective_day_bounds(
        open_from=date(2026, 4, 13),
        open_to=date(2026, 5, 29),
        today=date(2026, 4, 27),
    )
    assert min_day == date(2026, 4, 27)
    assert max_day == date(2026, 5, 29)
