from __future__ import annotations

from rich.console import Console
from rich.table import Table

from tc_sniper.models import QuizOption, Reservation, WatchLogEvent


def choose_quiz(console: Console, quizzes: list[QuizOption]) -> QuizOption:
    if not quizzes:
        raise RuntimeError("Na TCB strance nebyly nalezeny zadne testy.")
    if len(quizzes) == 1:
        quiz = quizzes[0]
        console.print(f"[green]Nalezen 1 test:[/green] {quiz.title}")
        return quiz

    table = Table(title="Nalezeny testy")
    table.add_column("#")
    table.add_column("Nazev")
    table.add_column("Quiz ID")
    for index, quiz in enumerate(quizzes, start=1):
        table.add_row(str(index), quiz.title, str(quiz.quiz_id))
    console.print(table)
    selection = int(console.input("Vyber test (cislo): "))
    if selection < 1 or selection > len(quizzes):
        raise RuntimeError("Neplatny vyber testu.")
    return quizzes[selection - 1]


def render_reservation(console: Console, reservation: Reservation) -> None:
    console.print(
        f"[yellow]Uz existuje rezervace:[/yellow] {reservation.day} {reservation.time}"
        + (f" (prijdte v {reservation.arrive_at})" if reservation.arrive_at else "")
    )


def render_watch_event(console: Console, event: WatchLogEvent) -> None:
    styles = {
        "info": "white",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "state": "cyan",
    }
    console.print(f"[{styles.get(event.level, 'white')}]{event.message}[/{styles.get(event.level, 'white')}]")
