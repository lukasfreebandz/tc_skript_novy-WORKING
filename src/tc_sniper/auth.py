from __future__ import annotations

from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from rich.console import Console

from tc_sniper.session_store import SessionStore
from tc_sniper.settings import STORAGE_STATE_PATH, ensure_app_dirs


def _launch_login_browser(playwright, console: Console):
    """Prefer bundled Playwright Chromium, then fall back to installed browsers."""
    attempts: list[tuple[str, dict[str, object]]] = [
        ("Playwright Chromium", {"headless": False}),
        ("Microsoft Edge", {"channel": "msedge", "headless": False}),
        ("Google Chrome", {"channel": "chrome", "headless": False}),
    ]
    errors: list[str] = []

    for label, kwargs in attempts:
        try:
            browser = playwright.chromium.launch(**kwargs)
            console.print(f"[green]Oteviram browser:[/green] {label}")
            return browser
        except Exception as exc:
            errors.append(f"{label}: {exc}")

    details = "\n".join(f" - {item}" for item in errors)
    raise RuntimeError(
        "Nepodarilo se otevrit zadny podporovany browser pro login.\n"
        "Zkus na cilovem PC nainstalovat Microsoft Edge nebo Google Chrome.\n"
        "Pokud chces pouzit Playwright Chromium, je potreba doinstalovat browser pres 'playwright install chromium'.\n"
        f"Detaily:\n{details}"
    )


def login_and_store_session(host: str, store: SessionStore, console: Console) -> None:
    ensure_app_dirs()
    login_url = f"https://{host}/my/"

    with sync_playwright() as playwright:
        browser = _launch_login_browser(playwright, console)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        console.print("[bold green]Prihlas se v otevrenem browser okne a pak se vrat do terminalu.[/bold green]")
        console.input("Stiskni Enter az budes prihlaseny: ")

        page.goto(login_url, wait_until="domcontentloaded")
        current = urlparse(page.url)
        cookies = context.cookies(f"https://{host}")
        has_moodle_session = any(cookie.get("name") == "MoodleSession" and cookie.get("value") for cookie in cookies)
        page_text = page.content()
        looks_logged_in = any(marker in page_text for marker in ("Uživatelské menu", "Odhlásit se", "Nástěnka", "usertext"))

        if current.hostname != host or "login" in current.path or not has_moodle_session or not looks_logged_in:
            browser.close()
            raise RuntimeError("Prihlaseni se nepodarilo potvrdit. Spust login znovu a dokoncete prihlaseni.")

        context.storage_state(path=str(STORAGE_STATE_PATH))
        browser.close()

    store.save(host)
