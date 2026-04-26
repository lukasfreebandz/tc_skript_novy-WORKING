from __future__ import annotations

import typer
from rich.console import Console

from tc_sniper.auth import login_and_store_session
from tc_sniper.client import MoodleTcbClient
from tc_sniper.models import WatchPreferences
from tc_sniper.parsing import parse_tcb_url
from tc_sniper.prompts import expand_days_input, parse_times_input
from tc_sniper.session_store import SessionStore
from tc_sniper.settings import APP_DIR
from tc_sniper.watcher import choose_quiz, watch_for_slot


app = typer.Typer(help="tc-sniper v2 CLI")
console = Console()
store = SessionStore()


@app.command()
def login(host: str = typer.Option("moodle.czu.cz", help="Target Moodle host.")) -> None:
    """Open a browser and save a logged-in Moodle session."""
    login_and_store_session(host, store, console)
    console.print(f"[green]Session ulozena.[/green] Data dir: {APP_DIR}")


@app.command()
def status() -> None:
    """Show whether a stored session exists and validate it."""
    session = store.load()
    if session is None:
        console.print("[yellow]Zadna ulozena session.[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"Host: {session.host}")
    console.print(f"Storage state: {session.storage_state_path}")
    client = MoodleTcbClient(store)
    try:
        if client.validate_session():
            console.print("[green]Session je platna.[/green]")
        else:
            console.print("[red]Session uz neni platna. Spust login znovu.[/red]")
            raise typer.Exit(code=1)
    finally:
        client.close()


@app.command()
def logout() -> None:
    """Delete stored local session files."""
    store.clear()
    console.print("[green]Lokalni session byla smazana.[/green]")


@app.command()
def watch() -> None:
    """Interactively choose a TCB quiz and watch for matching slots."""
    session = store.load()
    if session is None:
        console.print("[red]Nenalezena session. Spust nejdriv 'tc-sniper login'.[/red]")
        raise typer.Exit(code=1)

    client = MoodleTcbClient(store)
    try:
        tcb_url = console.input("Vloz odkaz na Testovaci centrum kurzu: ").strip()
        try:
            parse_tcb_url(tcb_url)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

        if not client.validate_session():
            console.print("[red]Session vyprsela. Spust nejdriv 'tc-sniper login'.[/red]")
            raise typer.Exit(code=1)

        course = client.fetch_course(tcb_url)
        quiz = choose_quiz(console, course)

        try:
            day_input = console.input(
                "Zadej dny (napr. 2026-05-30..2026-06-20 nebo 2026-30-05..2026-20-06): "
            ).strip()
            days = expand_days_input(day_input)

            mode = console.input("Casy zadas jako 'window' nebo 'list'? [window/list]: ").strip()
            if mode == "window":
                start = console.input("Cas OD (HH:MM): ").strip()
                end = console.input("Cas DO (HH:MM): ").strip()
                step = int(console.input("Krok v minutach: ").strip())
                times = parse_times_input("window", start, end, step)
            else:
                raw_times = console.input("Seznam casu (HH:MM) oddeleny carkami: ").strip()
                times = parse_times_input("list", raw_times)

            poll_interval = int(console.input("Interval mezi pruchody v sekundach [10]: ").strip() or "10")
        except ValueError as exc:
            console.print(f"[red]Neplatny vstup:[/red] {exc}")
            raise typer.Exit(code=1)

        preferences = WatchPreferences(
            tcb_url=tcb_url,
            quiz_id=quiz.quiz_id,
            quiz_title=quiz.title,
            days=days,
            times=times,
            poll_interval_seconds=poll_interval,
        )
        result = watch_for_slot(console, client, course, preferences)
        if result.status in {"booked", "reserved", "already_reserved"}:
            raise typer.Exit(code=0)
        raise typer.Exit(code=1)
    finally:
        client.close()


if __name__ == "__main__":
    app()
