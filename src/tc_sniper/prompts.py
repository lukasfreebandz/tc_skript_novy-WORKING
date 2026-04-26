from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_human_date(raw: str) -> date:
    value = raw.strip()
    if not value:
        raise ValueError("Datum nesmi byt prazdne.")

    candidates = (
        "%Y-%m-%d",
        "%Y-%d-%m",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
    )
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        "Neplatny format data. Pouzij napriklad 2026-05-30, 2026-30-05 nebo 30.05.2026."
    )


def expand_days_input(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    if ".." in raw:
        start_raw, end_raw = [part.strip() for part in raw.split("..", 1)]
        start = parse_human_date(start_raw)
        end = parse_human_date(end_raw)
        if end < start:
            raise ValueError("Konec rozsahu musi byt stejny nebo pozdejsi nez zacatek.")
        days: list[str] = []
        current = start
        while current <= end:
            days.append(current.isoformat())
            current += timedelta(days=1)
        return days
    return [parse_human_date(part.strip()).isoformat() for part in raw.split(",") if part.strip()]


def build_times_from_window(start_raw: str, end_raw: str, step_minutes: int) -> list[str]:
    if step_minutes <= 0:
        raise ValueError("Krok v minutach musi byt kladne cislo.")
    start = datetime.strptime(start_raw, "%H:%M")
    end = datetime.strptime(end_raw, "%H:%M")
    if end < start:
        raise ValueError("Cas DO musi byt stejny nebo pozdejsi nez cas OD.")
    items: list[str] = []
    current = start
    while current <= end:
        items.append(current.strftime("%H:%M"))
        current += timedelta(minutes=step_minutes)
    return items


def parse_times_input(mode: str, raw_value: str, window_end: str | None = None, step_minutes: int | None = None) -> list[str]:
    normalized = mode.strip().lower()
    if normalized == "list":
        times = [datetime.strptime(part.strip(), "%H:%M").strftime("%H:%M") for part in raw_value.split(",") if part.strip()]
        return times
    if normalized == "window":
        if window_end is None or step_minutes is None:
            raise ValueError("Window mod potrebuje konec intervalu a krok v minutach.")
        return build_times_from_window(raw_value, window_end, step_minutes)
    raise ValueError("Neznamy mod. Pouzij 'window' nebo 'list'.")
