import re
from datetime import datetime
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from app.agents.discovery.base import NormalizedJob
from app.config import BROWSER_SESSIONS_DIR, LINKEDIN_LOCATIONS, get_search_keywords, settings
from app.services.scraper_limits import wait as rate_wait


async def discover_linkedin_jobs(keywords: list[str] | None = None, location: str = "India") -> list[NormalizedJob]:
    """Search LinkedIn by role across India — returns jobs from ANY company."""
    keywords = keywords or get_search_keywords()[:8]
    locations = list(dict.fromkeys([location, *LINKEDIN_LOCATIONS]))[:4]
    all_jobs: list[NormalizedJob] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.playwright_headless)
        session_path = BROWSER_SESSIONS_DIR / "linkedin_discovery.json"
        context_kwargs = {"user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        if session_path.exists():
            context_kwargs["storage_state"] = str(session_path)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        for loc in locations:
            for keyword in keywords[:6]:
                url = (
                    "https://www.linkedin.com/jobs/search/?"
                    f"keywords={quote_plus(keyword)}&location={quote_plus(loc)}&f_TPR=r604800"
                )
                try:
                    await rate_wait("linkedin.com")
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1200)

                    cards = await page.query_selector_all("li.jobs-search-results__list-item, .job-search-card")
                    for card in cards[:15]:
                        job = await _parse_linkedin_card(card, keyword)
                        if job:
                            all_jobs.append(job)
                except Exception:
                    continue

        await context.storage_state(path=str(session_path))
        await browser.close()

    return _dedupe_jobs(all_jobs)


async def _parse_linkedin_card(card, keyword: str) -> NormalizedJob | None:
    try:
        title_el = await card.query_selector(".base-search-card__title, h3, .job-card-list__title")
        company_el = await card.query_selector(".base-search-card__subtitle, h4, .job-card-container__company-name")
        loc_el = await card.query_selector(".job-search-card__location, .job-card-container__metadata-item")
        link_el = await card.query_selector("a[href*='/jobs/view/']")

        title = (await title_el.inner_text()).strip() if title_el else None
        if not title:
            return None

        company = (await company_el.inner_text()).strip() if company_el else "Unknown"
        location = (await loc_el.inner_text()).strip() if loc_el else "India"
        url = await link_el.get_attribute("href") if link_el else None
        if not url:
            return None

        job_id_match = re.search(r"jobs/view/([^/?]+)", url)
        external_id = job_id_match.group(1) if job_id_match else re.sub(r"[^a-z0-9]", "-", title.lower())[:40]

        return NormalizedJob(
            external_id=f"linkedin:{external_id}",
            title=title,
            company=company,
            location=location,
            remote="remote" in location.lower() or "wfh" in location.lower(),
            salary_text=None,
            description=f"LinkedIn search: {keyword}",
            url=url.split("?")[0],
            source="linkedin",
            posted_at=datetime.utcnow(),
        )
    except Exception:
        return None


def _dedupe_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    seen: set[str] = set()
    result = []
    for job in jobs:
        key = f"{job.title.lower()}:{job.company.lower()}"
        if key not in seen:
            seen.add(key)
            result.append(job)
    return result
