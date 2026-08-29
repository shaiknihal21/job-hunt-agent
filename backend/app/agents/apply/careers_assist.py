"""Browser assist for company career pages (Amazon, Microsoft, Google, NVIDIA, etc.)."""

import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import BROWSER_SESSIONS_DIR
from app.services.browser_session import apply_resume_path, launch_browser

CAREERS_SOURCES = frozenset({"amazon", "microsoft", "google", "nvidia", "foundit"})


async def careers_assist_mode(job_url: str, resume_path: str, profile_data: dict) -> dict:
    """
    Open the job's careers page in Chrome, pre-upload resume if possible.
    User completes login + submit manually (Workday/Greenhouse blocks full automation).
    """
    session_path = BROWSER_SESSIONS_DIR / "careers.json"
    resume_file = apply_resume_path(resume_path)
    if not Path(resume_file).exists():
        resume_file = resume_path

    async with async_playwright() as p:
        browser = await launch_browser(p, headed=True)
        context_kwargs: dict = {
            "viewport": {"width": 1280, "height": 900},
            "locale": "en-IN",
        }
        if session_path.exists():
            context_kwargs["storage_state"] = str(session_path)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await page.goto(job_url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(3000)

        uploaded = False
        for selector in (
            "input[type='file']",
            "input[accept*='pdf']",
            "input[accept*='.pdf']",
        ):
            for file_input in await page.query_selector_all(selector):
                try:
                    await file_input.set_input_files(resume_file)
                    uploaded = True
                    await page.wait_for_timeout(2000)
                    break
                except Exception:
                    continue
            if uploaded:
                break

        # Try common "Apply" buttons to reach the form
        if not uploaded:
            for sel in (
                "a:has-text('Apply')",
                "button:has-text('Apply')",
                "a:has-text('Apply Now')",
                "button:has-text('Apply Now')",
            ):
                btn = await page.query_selector(sel)
                if btn:
                    try:
                        await btn.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        for file_input in await page.query_selector_all("input[type='file']"):
                            try:
                                await file_input.set_input_files(resume_file)
                                uploaded = True
                                break
                            except Exception:
                                continue
                    except Exception:
                        continue
                if uploaded:
                    break

        screenshot_dir = BROWSER_SESSIONS_DIR / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / f"careers_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)

        print(
            "\n  🌐 Careers page opened in Chrome.\n"
            "  → Log in if prompted, finish the form, and submit manually.\n"
            "  → Browser stays open for 3 minutes.\n",
            flush=True,
        )
        await page.wait_for_timeout(180000)

        try:
            await context.storage_state(path=str(session_path))
        except Exception:
            pass
        await browser.close()

        return {
            "mode": "careers_assist",
            "screenshot": str(screenshot_path),
            "resume_uploaded": uploaded,
            "submitted": False,
            "status": "prepared",
            "message": "Complete submit manually on the careers page",
        }


def run_careers_assist(job_url: str, resume_path: str, profile_data: dict) -> dict:
    return asyncio.run(careers_assist_mode(job_url, resume_path, profile_data))
