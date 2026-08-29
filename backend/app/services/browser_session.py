"""Shared Playwright session helpers for Naukri discovery + apply."""

from pathlib import Path

from playwright.async_api import Browser, Playwright

from app.config import BROWSER_SESSIONS_DIR, settings

NAUKRI_SESSION = BROWSER_SESSIONS_DIR / "naukri.json"

_STEALTH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
]


def naukri_context_kwargs(*, headed: bool = False) -> dict:
    kwargs: dict = {
        "user_agent": _STEALTH_UA,
        "viewport": {"width": 1280, "height": 900},
        "locale": "en-IN",
    }
    if NAUKRI_SESSION.exists():
        kwargs["storage_state"] = str(NAUKRI_SESSION)
    return kwargs


async def launch_browser(p: Playwright, *, headed: bool | None = None) -> Browser:
    """Prefer installed Google Chrome — Google SSO blocks bundled Chromium."""
    headless = settings.playwright_headless if headed is None else not headed
    launch_kwargs: dict = {"headless": headless, "args": _STEALTH_ARGS}
    try:
        return await p.chromium.launch(channel="chrome", **launch_kwargs)
    except Exception:
        return await p.chromium.launch(**launch_kwargs)


async def new_stealth_context(browser: Browser):
    context = await browser.new_context(**naukri_context_kwargs())
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return context


async def save_naukri_session(context) -> None:
    BROWSER_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(NAUKRI_SESSION))


def apply_resume_path(docx_path: str) -> str:
    """Prefer PDF sibling for portals that accept PDF uploads."""
    pdf = Path(docx_path).with_suffix(".pdf")
    if pdf.exists():
        return str(pdf)
    return docx_path


def naukri_temp_pdf_name(profile_data: dict) -> str:
    name = (profile_data.get("name") or "Resume").strip()
    safe = "".join(c if c.isalnum() else "" for c in name.split()[0]) or "Resume"
    return f"{safe}_Resume.pdf"
