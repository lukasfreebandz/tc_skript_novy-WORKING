from __future__ import annotations

import time

from rich.console import Console
from rich.table import Table

from tc_sniper.client import MoodleTcbClient
from tc_sniper.models import AvailableSlot, QuizOption, Reservation, TcbCourse, WatchPreferences, WatchResult
from tc_sniper.settings import append_event_log


def choose_quiz(console: Console, course: TcbCourse) -> QuizOption:
    if not course.quizzes:
        raise RuntimeError("Na TCB strance nebyly nalezeny zadne testy.")
    if len(course.quizzes) == 1:
        quiz = course.quizzes[0]
        suffix = []
        if quiz.open_from:
            suffix.append(f"od {quiz.open_from}")
        if quiz.open_to:
            suffix.append(f"do {quiz.open_to}")
        if quiz.duration:
            suffix.append(f"trvani {quiz.duration}")
        details = f" ({', '.join(suffix)})" if suffix else ""
        console.print(f"[green]Nalezen 1 test:[/green] {quiz.title}{details}")
        return quiz

    table = Table(title="Nalezeny testy")
    table.add_column("#")
    table.add_column("Nazev")
    table.add_column("Otevreni")
    table.add_column("Trvani")
    table.add_column("Quiz ID")
    for index, quiz in enumerate(course.quizzes, start=1):
        opening = "-"
        if quiz.open_from or quiz.open_to:
            opening = f"{quiz.open_from or '?'} -> {quiz.open_to or '?'}"
        table.add_row(
            str(index),
            quiz.title,
            opening,
            quiz.duration or "-",
            str(quiz.quiz_id),
        )
    console.print(table)
    selection = int(console.input("Vyber test (cislo): "))
    if selection < 1 or selection > len(course.quizzes):
        raise RuntimeError("Neplatny vyber testu.")
    return course.quizzes[selection - 1]


def render_reservation(console: Console, reservation: Reservation) -> None:
    console.print(
        f"[yellow]Uz existuje rezervace:[/yellow] {reservation.day} {reservation.time}"
        + (f" (prijdte v {reservation.arrive_at})" if reservation.arrive_at else "")
    )


def filter_matching_slots(slots: list[AvailableSlot], preferred_times: list[str]) -> list[AvailableSlot]:
    slot_map = {slot.time: slot for slot in slots}
    return [slot_map[time_label] for time_label in preferred_times if time_label in slot_map]


def watch_for_slot(console: Console, client: MoodleTcbClient, course: TcbCourse, preferences: WatchPreferences) -> WatchResult:
    quiz = next((item for item in course.quizzes if item.quiz_id == preferences.quiz_id), None)
    if quiz is None:
        raise RuntimeError("Vybrany test nebyl nalezen v discovery datech.")
    if quiz.reservation is not None:
        render_reservation(console, quiz.reservation)
        return WatchResult(status="already_reserved", message="Reservation already exists.", reservation=quiz.reservation)

    console.print(
        f"[bold]Hlida se test[/bold] {preferences.quiz_title} pro dny {', '.join(preferences.days)} "
        f"a casy {', '.join(preferences.times)}."
    )

    attempt = 0
    while True:
        attempt += 1
        console.print(f"[cyan]Pruchod #{attempt}[/cyan]")
        course = client.fetch_course(preferences.tcb_url)
        quiz = next((item for item in course.quizzes if item.quiz_id == preferences.quiz_id), None)
        if quiz is None:
            return WatchResult(status="error", message="Vybrany test uz na TCB strance neni.")
        if quiz.reservation is not None:
            render_reservation(console, quiz.reservation)
            return WatchResult(status="reserved", message="Reservation detected.", reservation=quiz.reservation)

        available_days = {day.date for day in quiz.available_days}
        checked_targets: list[str] = []
        for day in preferences.days:
            if day not in available_days:
                checked_targets.append(f"{day}: den neni dostupny")
                continue
            checked_targets.append(f"{day}: zkousim casy {', '.join(preferences.times)}")
            html_text, sesskey, slots = client.fetch_slots(course.tcb_id, preferences.quiz_id, day)
            matching = filter_matching_slots(slots, preferences.times)
            if not matching:
                checked_targets.append(f"{day}: zadny z preferovanych casu neni volny")
                continue
            target = matching[0]
            console.print(f"[green]Nalezen matching slot[/green] {day} {target.time} ({target.seats} mist). Rezervuji...")
            outcome = client.register(course.tcb_id, preferences.quiz_id, target.slot_id, target.day, sesskey)
            if outcome.ok and outcome.reservation is not None:
                append_event_log(
                    f"BOOKED quiz={preferences.quiz_id} day={outcome.reservation.day} time={outcome.reservation.time}"
                )
                render_reservation(console, outcome.reservation)
                return WatchResult(status="booked", message="Reservation created.", reservation=outcome.reservation)
            console.print("[red]Rezervace se nepodarila, watcher pokracuje.[/red]")
            break

        for line in checked_targets:
            console.print(f" - {line}")
        console.print(f"Bez shody, dalsi pokus za {preferences.poll_interval_seconds}s...")
        time.sleep(preferences.poll_interval_seconds)
