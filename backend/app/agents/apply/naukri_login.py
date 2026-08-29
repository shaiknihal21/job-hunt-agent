"""Open Naukri in a browser so the user can log in; cookies are saved for apply."""

import asyncio

from playwright.async_api import async_playwright

from app.services.browser_session import (
    NAUKRI_SESSION,
    launch_browser,
    new_stealth_context,
    save_naukri_session,
)


async def login_naukri_interactive() -> dict:
    """Headed browser — log in manually, then press Enter in the terminal."""
    print("\n   ┌─────────────────────────────────────────────────────┐")
    print("   │  Log in inside the BROWSER (email/password or OTP)   │")
    print("   │  Do NOT use 'Sign in with Google'                    │")
    print("   └─────────────────────────────────────────────────────┘")

    async with async_playwright() as p:
        browser = await launch_browser(p, headed=True)
        context = await new_stealth_context(browser)
        page = await context.new_page()
        await page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded", timeout=60000)

        print("\n   When you see your Naukri homepage in the browser,")
        print("   come back HERE and press Enter ONCE (empty line — don't type 'Enter').\n")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: input(">>> Press Enter here after login: "))

        await save_naukri_session(context)
        await browser.close()
        print("\n✅ Naukri session saved.")

    return {
        "status": "saved",
        "session_path": str(NAUKRI_SESSION),
        "message": "Naukri session saved — auto-apply will reuse these cookies.",
    }


def run_naukri_login() -> dict:
    return asyncio.run(login_naukri_interactive())
