import re
from datetime import datetime
from urllib.parse import quote_plus

import httpx
from playwright.async_api import async_playwright

from app.agents.discovery.base import NormalizedJob
from app.config import BROWSER_SESSIONS_DIR, get_search_keywords, settings


ENGINEERING_HINTS = ("engineer", "developer", "scientist", "architect", "analyst", "data", "ml", "ai", "software")


async def discover_microsoft_jobs(keywords: list[str] | None = None) -> list[NormalizedJob]:
    keywords = keywords or get_search_keywords()[:3]
    all_jobs: list[NormalizedJob] = []

    for keyword in keywords:
        jobs = await _fetch_microsoft_via_browser(keyword)
        all_jobs.extend(jobs)

    return _dedupe_jobs(all_jobs)


async def _fetch_microsoft_via_browser(keyword: str) -> list[NormalizedJob]:
    captured: dict | None = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.playwright_headless)
        session_path = BROWSER_SESSIONS_DIR / "microsoft.json"
        context_kwargs = {}
        if session_path.exists():
            context_kwargs["storage_state"] = str(session_path)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        async def on_response(response):
            nonlocal captured
            if "pcsx/search" in response.url and response.status == 200:
                try:
                    captured = await response.json()
                except Exception:
                    pass

        page.on("response", on_response)
        url = (
            "https://careers.microsoft.com/us/en/search-results?"
            f"keywords={quote_plus(keyword)}&location=India&country=India"
        )
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)
        except Exception:
            pass

        await context.storage_state(path=str(session_path))
        await browser.close()

    if not captured:
        return []

    positions = captured.get("data", {}).get("positions", [])
    jobs: list[NormalizedJob] = []
    for pos in positions:
        job = _parse_microsoft_position(pos, keyword)
        if job:
            jobs.append(job)
    return jobs


def _parse_microsoft_position(pos: dict, keyword: str) -> NormalizedJob | None:
    try:
        title = pos.get("name") or pos.get("title")
        if not title:
            return None

        title_lower = title.lower()
        if not any(h in title_lower for h in ENGINEERING_HINTS):
            return None

        locs = pos.get("standardizedLocations") or pos.get("locations") or []
        loc_text = ", ".join(str(loc) for loc in locs) if locs else "Multiple"
        india_eligible = (
            any("india" in str(loc).lower() for loc in locs)
            or "remote" in str(pos.get("workLocationOption", "")).lower()
            or not locs
        )
        if not india_eligible and any(re.search(r"\bUS\b|United States|Redmond", str(loc)) for loc in locs):
            return None

        job_id = str(pos.get("id") or pos.get("displayJobId") or title)
        path = pos.get("positionUrl") or f"/careers/job/{job_id}"
        url = path if path.startswith("http") else f"https://careers.microsoft.com{path}"

        return NormalizedJob(
            external_id=f"microsoft:{job_id}",
            title=title,
            company="Microsoft",
            location=loc_text,
            remote="remote" in loc_text.lower() or str(pos.get("workLocationOption", "")).lower() == "remote",
            salary_text=None,
            description=f"Microsoft careers search: {keyword}",
            url=url,
            source="microsoft",
            posted_at=datetime.utcnow(),
        )
    except Exception:
        return None


async def discover_google_jobs(keywords: list[str] | None = None) -> list[NormalizedJob]:
    """Google careers via public search page (API endpoint deprecated)."""
    keywords = keywords or get_search_keywords()[:3]
    all_jobs: list[NormalizedJob] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.playwright_headless)
        page = await browser.new_page()

        for keyword in keywords:
            url = (
                "https://www.google.com/about/careers/applications/jobs/results/?"
                f"location=India&q={quote_plus(keyword)}&sort_by=date"
            )
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                items = await page.query_selector_all("li.lLd3Je, [data-job-id], .lI7JobCardRoot")
                if not items:
                    items = await page.query_selector_all("a[href*='/jobs/results/']")

                for item in items[:10]:
                    job = await _parse_google_card(item, keyword, page)
                    if job:
                        all_jobs.append(job)
            except Exception:
                continue

        await browser.close()

    return _dedupe_jobs(all_jobs)


async def _parse_google_card(item, keyword: str, page) -> NormalizedJob | None:
    try:
        link = item if await item.get_attribute("href") else await item.query_selector("a[href*='/jobs/results/']")
        if not link:
            return None
        href = await link.get_attribute("href")
        title = (await link.inner_text()).strip()
        if not title or len(title) < 5 or title.lower() in {"learn more", "apply"}:
            return None

        job_id_match = re.search(r"/results/(\d+)", href or "")
        job_id = job_id_match.group(1) if job_id_match else re.sub(r"[^a-z0-9-]", "-", title.lower())[:30]
        url = href if href.startswith("http") else f"https://www.google.com/about/careers/applications{href}"

        return NormalizedJob(
            external_id=f"google:{job_id}",
            title=title,
            company="Google",
            location="India",
            remote=False,
            salary_text=None,
            description=f"Google careers search: {keyword}",
            url=url,
            source="google",
            posted_at=datetime.utcnow(),
        )
    except Exception:
        return None


async def discover_nvidia_jobs(keywords: list[str] | None = None) -> list[NormalizedJob]:
    keywords = keywords or ["AI Engineer", "Machine Learning Engineer", "Software Engineer"]
    all_jobs: list[NormalizedJob] = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for keyword in keywords:
            url = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
            try:
                response = await client.post(
                    url,
                    json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": keyword},
                    headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                )
                if response.status_code != 200:
                    continue
                for item in response.json().get("jobPostings", []):
                    job = _parse_workday_item(item, "NVIDIA", "nvidia", keyword)
                    if job:
                        all_jobs.append(job)
            except Exception:
                continue

    return _dedupe_jobs(all_jobs)[:15]


def _parse_workday_item(item: dict, company: str, source: str, keyword: str) -> NormalizedJob | None:
    try:
        title = item.get("title")
        if not title:
            return None
        path = item.get("externalPath") or item.get("bulletFields", [""])[0]
        loc = item.get("locationsText") or item.get("location") or "Multiple"
        job_id = str(item.get("bulletFields", [title])[0] if item.get("bulletFields") else hash(title))
        url = f"https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite{path}" if path else ""

        return NormalizedJob(
            external_id=f"{source}:{job_id}",
            title=title,
            company=company,
            location=str(loc),
            remote="remote" in str(loc).lower(),
            salary_text=None,
            description=f"{company} careers: {keyword}",
            url=url or f"https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
            source=source,
            posted_at=datetime.utcnow(),
        )
    except Exception:
        return None


async def discover_foundit_jobs(keywords: list[str] | None = None) -> list[NormalizedJob]:
    from app.config import SEARCH_LOCATIONS

    keywords = keywords or get_search_keywords()[:3]
    all_jobs: list[NormalizedJob] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.playwright_headless)
        page = await browser.new_page()

        for keyword in keywords:
            for loc in SEARCH_LOCATIONS[:4]:
                slug = keyword.lower().replace(" ", "-")
                loc_slug = loc.lower().replace(" ", "-")
                url = f"https://www.foundit.in/search/{slug}-jobs-in-{loc_slug}"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(2000)
                    cards = await page.query_selector_all("div.jobTuple, article.jobCard, [class*='job-card']")
                    for card in cards[:8]:
                        job = await _parse_foundit_card(card, keyword, loc)
                        if job:
                            all_jobs.append(job)
                except Exception:
                    continue

        await browser.close()

    return _dedupe_jobs(all_jobs)


async def _parse_foundit_card(card, keyword: str, location: str) -> NormalizedJob | None:
    try:
        title_el = await card.query_selector("h2 a, .jobTitle, a.title")
        company_el = await card.query_selector(".companyName, .company, [class*='company']")
        if not title_el:
            return None
        title = (await title_el.inner_text()).strip()
        url = await title_el.get_attribute("href")
        company = (await company_el.inner_text()).strip() if company_el else "Unknown"
        external_id = re.sub(r"[^a-z0-9-]", "-", f"{title}-{company}".lower())[:50]
        return NormalizedJob(
            external_id=f"foundit:{external_id}",
            title=title,
            company=company,
            location=location,
            remote="remote" in location.lower(),
            salary_text=None,
            description=f"Foundit search: {keyword}",
            url=url if url and url.startswith("http") else f"https://www.foundit.in{url or ''}",
            source="foundit",
            posted_at=datetime.utcnow(),
        )
    except Exception:
        return None


def _dedupe_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    seen: set[str] = set()
    result = []
    for job in jobs:
        key = f"{job.source}:{job.external_id}"
        if key not in seen:
            seen.add(key)
            result.append(job)
    return result
