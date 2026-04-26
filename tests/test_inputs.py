from tc_sniper.prompts import build_times_from_window, expand_days_input, parse_human_date, parse_times_input


def test_expand_days_range() -> None:
    assert expand_days_input("2026-05-02..2026-05-04") == ["2026-05-02", "2026-05-03", "2026-05-04"]


def test_expand_days_range_accepts_year_day_month() -> None:
    days = expand_days_input("2026-30-05..2026-20-06")
    assert days[0] == "2026-05-30"
    assert days[-1] == "2026-06-20"
    assert len(days) == 22


def test_expand_days_list() -> None:
    assert expand_days_input("2026-05-02,2026-05-04") == ["2026-05-02", "2026-05-04"]


def test_parse_human_date_accepts_czech_style() -> None:
    assert parse_human_date("30.05.2026").isoformat() == "2026-05-30"


def test_build_times_from_window() -> None:
    assert build_times_from_window("14:20", "14:50", 10) == ["14:20", "14:30", "14:40", "14:50"]


def test_parse_times_list_mode() -> None:
    assert parse_times_input("list", "08:40,14:30") == ["08:40", "14:30"]
