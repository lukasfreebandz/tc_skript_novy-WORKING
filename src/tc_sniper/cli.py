from __future__ import annotations

from threading import Event

import typer
from rich.console import Console

from tc_sniper.auth import login_and_store_session
from tc_sniper.models import WatchStartRequest
from tc_sniper.services import AppServices
from tc_sniper.watcher import choose_quiz, render_reservation, render_watch_event


app = typer.Typer(help="tc-sniper v2 CLI")
console = Console()
services = AppServices()


@app.command()
def login(host: str = typer.Option("moodle.czu.cz", help="Target Moodle host.")) -> None:
    """Open a browser and save a logged-in Moodle session."""
    login_and_store_session(host, services.store, console)
    console.print("[green]Session ulozena.[/green]")


@app.command()
def status() -> None:
    """Show whether a stored session exists and validate it."""
    session_status = services.session.get_status(revalidate=True)
    if session_status.host:
        console.print(f"Host: {session_status.host}")
    if session_status.storage_state_path:
        console.print(f"Storage state: {session_status.storage_state_path}")
    if session_status.status == "valid":
        console.print("[green]Session je platna.[/green]")
        return
    console.print(f"[red]{session_status.message}[/red]")
    raise typer.Exit(code=1)


@app.command()
def logout() -> None:
    """Delete stored local session files."""
    services.session.logout()
    console.print("[green]Lokalni session byla smazana.[/green]")


@app.command()
def watch() -> None:
    """Interactively choose a TCB quiz and watch for matching slots."""
    session_status = services.session.get_status(revalidate=False)
    if session_status.status == "logged_out":
        console.print("[red]Nenalezena session. Spust nejdriv 'tc-sniper login'.[/red]")
        raise typer.Exit(code=1)

    tcb_url = console.input("Vloz odkaz na Testovaci centrum kurzu: ").strip()
    try:
        course = services.courses.discover(tcb_url)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    quiz = choose_quiz(console, course.quizzes)
    if quiz.reservation is not None:
        render_reservation(console, quiz.reservation)
        raise typer.Exit(code=0)

    try:
        day_input = console.input(
            "Zadej dny (napr. 2026-05-30..2026-06-20 nebo 2026-30-05..2026-20-06): "
        ).strip()
        mode = console.input("Casy zadas jako 'window' nebo 'list'? [window/list]: ").strip()
        if mode == "window":
            start = console.input("Cas OD (HH:MM): ").strip()
            end = console.input("Cas DO (HH:MM): ").strip()
            step = int(console.input("Krok v minutach: ").strip())
            request = WatchStartRequest(
                tcb_url=tcb_url,
                quiz_id=quiz.quiz_id,
                quiz_title=quiz.title,
                day_mode="range" if ".." in day_input else "list",
                days_raw=day_input,
                time_mode="window",
                window_start=start,
                window_end=end,
                window_step_minutes=step,
                poll_interval_seconds=int(console.input("Interval mezi pruchody v sekundach [10]: ").strip() or "10"),
            )
        else:
            raw_times = console.input("Seznam casu (HH:MM) oddeleny carkami: ").strip()
            request = WatchStartRequest(
                tcb_url=tcb_url,
                quiz_id=quiz.quiz_id,
                quiz_title=quiz.title,
                day_mode="range" if ".." in day_input else "list",
                days_raw=day_input,
                time_mode="list",
                times_raw=raw_times,
                poll_interval_seconds=int(console.input("Interval mezi pruchody v sekundach [10]: ").strip() or "10"),
            )
        preferences = services.watch.prepare_preferences_with_course_validation(request)
    except ValueError as exc:
        console.print(f"[red]Neplatny vstup:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"[bold]Hlida se test[/bold] {preferences.quiz_title} pro dny {', '.join(preferences.days)} "
        f"a casy {', '.join(preferences.times)}."
    )
    result = services.watch.run_blocking(preferences, on_log=lambda event: render_watch_event(console, event), stop_event=Event())
    if result.reservation is not None:
        render_reservation(console, result.reservation)
    raise typer.Exit(code=0 if result.status in {"booked", "already_reserved", "stopped"} else 1)


if __name__ == "__main__":
    app()
