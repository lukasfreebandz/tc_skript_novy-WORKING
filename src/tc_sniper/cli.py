from __future__ import annotations

from datetime import timedelta
from datetime import datetime
from pathlib import Path
import sys

import typer
from rich.console import Console

from tc_sniper.auth import login_and_store_session
from tc_sniper.client import MoodleTcbClient
from tc_sniper.models import WatchPreferences
from tc_sniper.parsing import parse_tcb_url
from tc_sniper.prompts import (
    compute_effective_day_bounds,
    expand_days_input,
    parse_quiz_open_date,
    parse_times_input,
    validate_days_within_bounds,
)
from tc_sniper.session_store import SessionStore
from tc_sniper.settings import APP_DIR
from tc_sniper.watcher import choose_quiz, watch_for_slot


app = typer.Typer(help="tc-sniper v2 CLI", invoke_without_command=True)
console = Console()
store = SessionStore()
APP_VERSION = "0.1.0"
BUILD_ID = "2026-04-27-2043-rangefix"


def print_build_info() -> None:
    target = Path(sys.executable if getattr(sys, "frozen", False) else __file__)
    build_stamp = datetime.fromtimestamp(target.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"[dim]tc-sniper v2 | verze {APP_VERSION} | build {build_stamp} | id {BUILD_ID}[/dim]")


def run_login(host: str = "moodle.czu.cz") -> None:
    """Open a browser and save a logged-in Moodle session."""
    login_and_store_session(host, store, console)
    console.print(f"[green]Session ulozena.[/green] Data dir: {APP_DIR}")


def run_watch() -> None:
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
        raw_min_day = parse_quiz_open_date(quiz.open_from)
        max_day = parse_quiz_open_date(quiz.open_to)
        min_day, max_day = compute_effective_day_bounds(raw_min_day, max_day)

        if max_day is not None and min_day > max_day:
            console.print(
                f"[red]Test uz nema zadny platny interval pro vyber dne.[/red] "
                f"Dnes je {datetime.now().date().isoformat()}, test byl otevren nejpozdeji do {max_day.isoformat()}."
            )
            raise typer.Exit(code=1)

        try:
            if min_day is not None or max_day is not None:
                console.print(
                    "[cyan]Povoleny rozsah dnu pro vybrany test:[/cyan] "
                    f"{min_day.isoformat() if min_day else '?'} .. {max_day.isoformat() if max_day else '?'}"
                )
            console.print(
                "[cyan]Pouziti formatu:[/cyan] '..' = souvisly rozsah dnu, ',' = jednotlive konkretni dny"
            )
            range_example = "2026-05-30..2026-06-20"
            list_example = "2026-05-30,2026-06-03"
            if min_day is not None and max_day is not None:
                range_example = f"{min_day.isoformat()}..{max_day.isoformat()}"
                second_day = min(min_day + timedelta(days=3), max_day)
                list_example = f"{min_day.isoformat()},{second_day.isoformat()}"
            elif min_day is not None:
                range_example = f"{min_day.isoformat()}..{(min_day + timedelta(days=7)).isoformat()}"
                list_example = f"{min_day.isoformat()},{(min_day + timedelta(days=3)).isoformat()}"
            elif max_day is not None:
                first_day = max_day - timedelta(days=7)
                range_example = f"{first_day.isoformat()}..{max_day.isoformat()}"
                second_day = max_day - timedelta(days=3)
                list_example = f"{first_day.isoformat()},{second_day.isoformat()}"
            day_prompt = (
                "Zadej dny ve formatu YYYY-MM-DD "
                f"(rozsah: {range_example}, jednotlive dny: {list_example}): "
            )
            day_input = console.input(day_prompt).strip()
            days = expand_days_input(day_input)
            validate_days_within_bounds(days, min_day=min_day, max_day=max_day)

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


def ensure_logged_in(host: str = "moodle.czu.cz") -> None:
    """Reuse a valid stored session when available, otherwise start login."""
    session = store.load()
    if session is not None:
        try:
            client = MoodleTcbClient(store)
        except RuntimeError:
            client = None
        if client is not None:
            try:
                if client.validate_session():
                    console.print("[green]Nalezena platna session, login preskakuji.[/green]")
                    return
                console.print("[yellow]Ulozena session uz neni platna, otevru novy login.[/yellow]")
            finally:
                client.close()

    run_login(host)


def run_default_flow() -> None:
    """Default double-click flow for the packaged exe."""
    console.print("[bold]Spoustim vychozi flow:[/bold] login -> watch")
    ensure_logged_in()
    run_watch()


@app.callback()
def main(ctx: typer.Context) -> None:
    """Run login -> watch when the app is opened without a command."""
    print_build_info()
    if ctx.invoked_subcommand is not None:
        return

    exit_code = 0
    try:
        run_default_flow()
    except typer.Exit as exc:
        exit_code = exc.exit_code
    finally:
        console.input("Stiskni Enter pro ukonceni...")
    raise typer.Exit(code=exit_code)


@app.command()
def login(host: str = typer.Option("moodle.czu.cz", help="Target Moodle host.")) -> None:
    """Open a browser and save a logged-in Moodle session."""
    run_login(host)


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
    run_watch()


if __name__ == "__main__":
    app()
