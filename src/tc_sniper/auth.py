from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, sync_playwright
from rich.console import Console

from tc_sniper.session_store import SessionStore
from tc_sniper.settings import STORAGE_STATE_PATH, ensure_app_dirs


def page_looks_logged_in(page_text: str) -> bool:
    markers = ("usertext", "/login/logout.php", "action-menu-toggle-0", "Uživatelské menu", "Odhlásit se")
    return any(marker in page_text for marker in markers)


def validate_logged_in_session(context: BrowserContext, page: Page, host: str) -> None:
    login_url = f"https://{host}/my/"
    page.goto(login_url, wait_until="domcontentloaded")
    current = urlparse(page.url)
    cookies = context.cookies(f"https://{host}")
    has_moodle_session = any(cookie.get("name") == "MoodleSession" and cookie.get("value") for cookie in cookies)
    page_text = page.content()

    if current.hostname != host or "login" in current.path or not has_moodle_session or not page_looks_logged_in(page_text):
        raise RuntimeError("Prihlaseni se nepodarilo potvrdit. Spust login znovu a dokoncete prihlaseni.")


def run_login_flow(
    host: str,
    store: SessionStore,
    wait_for_confirmation: Callable[[], None],
    on_browser_opened: Callable[[], None] | None = None,
    on_completing: Callable[[], None] | None = None,
) -> None:
    ensure_app_dirs()
    login_url = f"https://{host}/my/"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")

        if on_browser_opened is not None:
            on_browser_opened()

        wait_for_confirmation()

        if on_completing is not None:
            on_completing()

        validate_logged_in_session(context, page, host)
        context.storage_state(path=str(STORAGE_STATE_PATH))
        browser.close()

    store.save(host)


def login_and_store_session(host: str, store: SessionStore, console: Console) -> None:
    console.print("[bold green]Prihlas se v otevrenem browser okne a pak se vrat do terminalu.[/bold green]")
    run_login_flow(
        host=host,
        store=store,
        wait_for_confirmation=lambda: console.input("Stiskni Enter az budes prihlaseny: "),
    )
