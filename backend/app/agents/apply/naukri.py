import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page, async_playwright

from app.agents.apply.naukri_screening import answer_for_question
from app.config import BROWSER_SESSIONS_DIR
from app.services.browser_session import launch_browser, new_stealth_context, save_naukri_session
from app.services.resume.naukri_pdf import naukri_upload_candidates, prepare_naukri_upload_file

CHATBOT = "._chatBotContainer, [id*='ChatbotContainer'], [class*='chatBotContainer']"


async def _chatbot_visible(page: Page) -> bool:
    overlay = await page.query_selector(".chatbot_Overlay.show, .chatbot_Overlay")
    if overlay:
        return True
    root = await page.query_selector(CHATBOT)
    return root is not None


async def _chatbot_text(page: Page) -> str:
    root = await page.query_selector(CHATBOT)
    if not root:
        return ""
    try:
        return await root.inner_text()
    except Exception:
        return ""


async def _chatbot_input(page: Page):
    for sel in (
        f"{CHATBOT} textarea",
        f"{CHATBOT} input[type='text']",
        f"{CHATBOT} input[type='number']",
        f"{CHATBOT} input:not([type='hidden']):not([type='file'])",
    ):
        el = await page.query_selector(sel)
        if el:
            return el
    return None


async def _chatbot_send(page: Page) -> bool:
    for sel in (
        f"{CHATBOT} button:has-text('Send')",
        f"{CHATBOT} button:has-text('Submit')",
        f"{CHATBOT} button:has-text('Next')",
        f"{CHATBOT} [class*='sendBtn']",
        f"{CHATBOT} button[type='submit']",
    ):
        btn = await page.query_selector(sel)
        if btn:
            try:
                await btn.click(timeout=5000)
                return True
            except Exception:
                continue
    return False


async def _chatbot_submit(page: Page) -> bool:
    for sel in (
        f"{CHATBOT} button:has-text('Submit')",
        f"{CHATBOT} button:has-text('Apply')",
        f"{CHATBOT} button:has-text('Done')",
    ):
        btn = await page.query_selector(sel)
        if btn:
            try:
                await btn.click(timeout=5000)
                return True
            except Exception:
                continue
    return False


async def _dismiss_chatbot_overlay(page: Page) -> bool:
    for sel in (
        f"{CHATBOT} button[aria-label='Close']",
        f"{CHATBOT} [class*='close']",
        ".chatbot_Overlay + button",
    ):
        btn = await page.query_selector(sel)
        if btn:
            try:
                await btn.click(timeout=3000)
                await page.wait_for_timeout(500)
                return True
            except Exception:
                continue
    return False


async def _upload_failed(page: Page) -> bool:
    text = (await _chatbot_text(page)).lower()
    try:
        text += " " + (await page.inner_text("body")).lower()
    except Exception:
        pass
    return any(
        x in text
        for x in (
            "file upload was unsuccessful",
            "upload was unsuccessful",
            "file upload unsuccessful",
            "could not upload",
            "invalid file",
        )
    )


async def _upload_in_chatbot(page: Page, resume_path: str, profile_data: dict) -> str | None:
    """Upload repaired PDF — master resume first. Uses file-chooser + direct input."""
    candidates = naukri_upload_candidates(resume_path)
    if not candidates:
        return None

    profile_name = profile_data.get("name") or "Resume"

    for src in candidates:
        try:
            upload_file = prepare_naukri_upload_file(src, profile_name)
        except Exception:
            continue

        # Method 1: click Upload/Attach in chatbot → file chooser (closest to real user)
        for trigger in (
            f"{CHATBOT} >> text=/upload/i",
            f"{CHATBOT} >> text=/attach/i",
            f"{CHATBOT} >> text=/browse/i",
            f"{CHATBOT} [class*='upload' i]",
            f"{CHATBOT} label[for*='file' i]",
        ):
            try:
                loc = page.locator(trigger).first
                if await loc.count() == 0:
                    continue
                async with page.expect_file_chooser(timeout=8000) as fc_info:
                    await loc.click(timeout=5000)
                chooser = await fc_info.value
                await chooser.set_files(str(upload_file))
                await page.wait_for_timeout(6000)
                if not await _upload_failed(page):
                    return str(upload_file)
            except Exception:
                continue

        # Method 2: set files on hidden input inside chatbot
        for file_input in await page.query_selector_all(f"{CHATBOT} input[type='file']"):
            try:
                await file_input.set_input_files(str(upload_file))
                await page.wait_for_timeout(6000)
                if not await _upload_failed(page):
                    return str(upload_file)
            except Exception:
                continue

        # Method 3: any page-level file input (last resort)
        for file_input in await page.query_selector_all("input[type='file']"):
            try:
                await file_input.set_input_files(str(upload_file))
                await page.wait_for_timeout(6000)
                if not await _upload_failed(page):
                    return str(upload_file)
            except Exception:
                continue

    return None


async def _upload_to_naukri_profile(page: Page, resume_path: str, profile_data: dict) -> str | None:
    """Pre-upload repaired master PDF to Naukri profile — chatbot often uses profile resume."""
    candidates = naukri_upload_candidates(resume_path)
    if not candidates:
        return None
    src = candidates[0]  # master first
    try:
        upload_file = prepare_naukri_upload_file(src, profile_data.get("name") or "Resume")
    except Exception:
        return None

    try:
        await page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        for sel in ("input[type='file']", "input[accept*='pdf']"):
            for inp in await page.query_selector_all(sel):
                try:
                    await inp.set_input_files(str(upload_file))
                    await page.wait_for_timeout(5000)
                    return str(upload_file)
                except Exception:
                    continue
    except Exception:
        pass
    return None


async def _complete_chatbot_flow(page: Page, profile_data: dict, resume_path: str, rounds: int = 15) -> list[str]:
    """Answer Naukri recruiter chatbot until it closes or rounds exhausted."""
    log: list[str] = []

    for _ in range(rounds):
        await page.wait_for_timeout(1800)
        if not await _chatbot_visible(page):
            break

        text = await _chatbot_text(page)
        lower = text.lower()

        if "file upload was unsuccessful" in lower or "upload" in lower:
            up = await _upload_in_chatbot(page, resume_path, profile_data)
            if up:
                log.append(f"uploaded: {up}")
                await page.wait_for_timeout(2000)
                continue

        questions = [ln.strip() for ln in text.splitlines() if "?" in ln]
        ans = None
        for q in reversed(questions):
            ans = answer_for_question(q, profile_data)
            if ans:
                log.append(f"Q: {q[:50]} → {ans}")
                break

        if not ans and any(k in lower for k in ("experience", "how many years", "years of")):
            years = str((profile_data.get("application_defaults") or {}).get("years_experience", 1))
            ans = years
            log.append(f"default years → {ans}")

        if ans:
            inp = await _chatbot_input(page)
            if inp:
                try:
                    await inp.fill(ans)
                    await page.wait_for_timeout(300)
                    if not await _chatbot_send(page):
                        await page.keyboard.press("Enter")
                    await page.wait_for_timeout(2000)
                    continue
                except Exception:
                    pass

        # Nothing to answer — try upload if file input visible
        if await page.query_selector(f"{CHATBOT} input[type='file']"):
            up = await _upload_in_chatbot(page, resume_path, profile_data)
            if up:
                log.append(f"uploaded: {up}")
                await page.wait_for_timeout(2000)

    return log


async def _detect_submit_success(page: Page) -> bool:
    if await _chatbot_visible(page):
        return False
    chat = (await _chatbot_text(page)).lower()
    try:
        body = (await page.inner_text("body")).lower()
    except Exception:
        body = ""
    combined = chat + " " + body
    success_phrases = (
        "successfully applied to this job",
        "you have successfully applied",
        "application submitted successfully",
        "your application has been submitted",
    )
    return any(p in combined for p in success_phrases)


async def prepare_naukri_application(
    job_url: str,
    resume_path: str,
    profile_data: dict,
    submit: bool = False,
) -> dict:
    """Fill Naukri apply flow — handles recruiter chatbot overlay."""
    async with async_playwright() as p:
        browser = await launch_browser(p)
        context = await new_stealth_context(browser)
        page = await context.new_page()

        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)

        filled_fields: dict[str, str] = {}

        # Pre-sync master resume to Naukri profile (helps chatbot accept upload)
        profile_upload = await _upload_to_naukri_profile(page, resume_path, profile_data)
        if profile_upload:
            filled_fields["profile_resume"] = profile_upload
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)

        for selector in (
            "button#apply-button",
            ".apply-button",
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "a:has-text('Apply')",
        ):
            btn = await page.query_selector(selector)
            if btn:
                try:
                    await btn.click(timeout=10000)
                    await page.wait_for_timeout(3500)
                    break
                except Exception:
                    continue

        screening = await _complete_chatbot_flow(page, profile_data, resume_path)

        if not screening:
            uploaded = await _upload_in_chatbot(page, resume_path, profile_data)
            if uploaded:
                filled_fields["resume"] = uploaded
                screening.extend(await _complete_chatbot_flow(page, profile_data, resume_path, rounds=8))

        screenshot_dir = BROWSER_SESSIONS_DIR / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        screenshot_path = screenshot_dir / f"apply_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)

        submitted = False
        if submit:
            # Wait for chatbot to finish — do NOT click page submit while overlay blocks
            if await _chatbot_visible(page):
                screening.extend(await _complete_chatbot_flow(page, profile_data, resume_path, rounds=10))
                if await _chatbot_submit(page):
                    await page.wait_for_timeout(3000)

            if not submitted and not await _chatbot_visible(page):
                for selector in (
                    "button[type='submit']",
                    "button:has-text('Submit')",
                    "button:has-text('Apply')",
                ):
                    btn = await page.query_selector(selector)
                    if btn:
                        try:
                            await btn.click(timeout=8000)
                            await page.wait_for_timeout(3000)
                            break
                        except Exception:
                            continue

            submitted = await _detect_submit_success(page)

            await page.screenshot(path=str(screenshot_path.with_name(screenshot_path.stem + "_done.png")))

        if submit and not submitted:
            await page.wait_for_timeout(8000)

        await save_naukri_session(context)
        await browser.close()

        return {
            "filled_fields": filled_fields,
            "screening_answers": screening,
            "screenshot": str(screenshot_path),
            "submitted": submitted,
            "status": "applied" if submitted else "prepared",
        }


def run_naukri_apply(job_url: str, resume_path: str, profile_data: dict, submit: bool = False) -> dict:
    return asyncio.run(prepare_naukri_application(job_url, resume_path, profile_data, submit))


async def naukri_assist_mode(
    job_url: str,
    resume_path: str,
    profile_data: dict,
    *,
    wait_sec: int | None = None,
    cheatsheet: list[str] | None = None,
) -> dict:
    """
    Reliable Naukri apply: open job in Chrome, show screening cheatsheet, you finish in browser.
    Does NOT claim success — run `track #N applied` after you submit.
    """
    from app.config import settings
    from app.services.apply_assist import build_cheatsheet
    from app.services.resume.naukri_pdf import naukri_upload_candidates, prepare_naukri_upload_file

    wait = wait_sec or settings.assisted_apply_wait_sec
    sheet = cheatsheet or build_cheatsheet(profile_data)

    async with async_playwright() as p:
        browser = await launch_browser(p, headed=True)
        context = await new_stealth_context(browser)
        page = await context.new_page()

        await page.goto(job_url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(3000)

        if "login" in page.url.lower():
            print("\n⚠️  Not logged in to Naukri. Log in in the browser window.", flush=True)
            print("   (Or run: ./run.sh login naukri first)\n", flush=True)
            await page.wait_for_timeout(60000)

        for selector in (
            "button#apply-button",
            ".apply-button",
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
        ):
            btn = await page.query_selector(selector)
            if btn:
                try:
                    await btn.click(timeout=8000)
                    await page.wait_for_timeout(3000)
                    break
                except Exception:
                    continue

        resume_hint = resume_path
        candidates = naukri_upload_candidates(resume_path)
        if candidates:
            try:
                resume_hint = str(prepare_naukri_upload_file(candidates[0], profile_data.get("name") or "Resume"))
            except Exception:
                resume_hint = str(candidates[0])

        print("\n" + "=" * 52, flush=True)
        print("  NAUKRI APPLY — finish in the browser window", flush=True)
        print("=" * 52, flush=True)
        print(f"  Job: {job_url[:70]}...", flush=True)
        print(f"  Resume file: {resume_hint}", flush=True)
        print("\n  Screening answers (type these in chatbot):", flush=True)
        for line in sheet:
            print(f"    • {line}", flush=True)
        print(f"\n  Browser stays open {wait}s. Then run:", flush=True)
        print("    ./run.sh track #ID applied", flush=True)
        print("=" * 52 + "\n", flush=True)

        screenshot_dir = BROWSER_SESSIONS_DIR / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        screenshot_path = screenshot_dir / f"naukri_assist_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        await page.wait_for_timeout(wait * 1000)

        await save_naukri_session(context)
        await browser.close()

        return {
            "mode": "naukri_assist",
            "submitted": False,
            "status": "awaiting_user",
            "cheatsheet": sheet,
            "resume_path": resume_hint,
            "screenshot": str(screenshot_path),
        }


def run_naukri_assist(job_url: str, resume_path: str, profile_data: dict, **kwargs) -> dict:
    return asyncio.run(naukri_assist_mode(job_url, resume_path, profile_data, **kwargs))


async def linkedin_assist_mode(job_url: str, resume_path: str, profile_data: dict) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        session_path = BROWSER_SESSIONS_DIR / "linkedin.json"
        context_kwargs = {"viewport": {"width": 1280, "height": 900}}
        if session_path.exists():
            context_kwargs["storage_state"] = str(session_path)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)

        file_input = await page.query_selector("input[type='file']")
        if file_input and Path(resume_path).exists():
            await file_input.set_input_files(resume_path)

        screenshot_dir = BROWSER_SESSIONS_DIR / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        screenshot_path = screenshot_dir / f"linkedin_assist_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=str(screenshot_path))
        await page.wait_for_timeout(120000)
        await context.storage_state(path=str(session_path))
        await browser.close()

        return {
            "mode": "linkedin_assist",
            "screenshot": str(screenshot_path),
            "submitted": False,
            "message": "Screenshot saved — complete submit manually in browser if needed",
        }
