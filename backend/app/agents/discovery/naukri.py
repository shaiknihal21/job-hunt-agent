import asyncio
import re
from datetime import datetime
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from app.agents.discovery.base import NormalizedJob
from app.config import SEARCH_LOCATIONS, get_search_keywords, settings
from app.services.browser_session import launch_browser, new_stealth_context, save_naukri_session
from app.services.salary import parse_salary_lpa
from app.services.scraper_limits import wait as rate_wait


async def discover_naukri_jobs(keywords: list[str] | None = None, location: str = "Hyderabad") -> list[NormalizedJob]:
    keywords = keywords or get_search_keywords()[:6]
    locations = list(dict.fromkeys([location, *SEARCH_LOCATIONS]))[:4]
    all_jobs: list[NormalizedJob] = []

    async with async_playwright() as p:
        browser = await launch_browser(p)
        context = await new_stealth_context(browser)
        page = await context.new_page()

        for loc in locations:
            for keyword in keywords:
                slug = keyword.lower().replace(" ", "-")
                loc_slug = loc.lower().replace(" ", "-")
                search_url = f"https://www.naukri.com/{quote_plus(slug)}-jobs-in-{quote_plus(loc_slug)}"
                try:
                    await rate_wait("naukri.com")
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(800)

                    cards = await page.query_selector_all("article.jobTuple, div.srp-jobtuple-wrapper, .cust-job-tuple")
                    if not cards:
                        cards = await page.query_selector_all("[class*='jobTuple'], [class*='srp-jobtuple']")

                    for card in cards[:10]:
                        job = await _parse_naukri_card(card, keyword)
                        if job:
                            all_jobs.append(job)
                except Exception:
                    continue

        # Enrich salary + description from detail pages (list cards often omit salary)
        enriched: list[NormalizedJob] = []
        seen_urls: set[str] = set()
        enrich_budget = settings.naukri_enrich_max
        for job in all_jobs:
            if job.url in seen_urls:
                continue
            seen_urls.add(job.url)
            if _needs_enrichment(job) and enrich_budget > 0:
                try:
                    job = await _enrich_naukri_detail(page, job)
                    enrich_budget -= 1
                except Exception:
                    pass
            enriched.append(job)

        await save_naukri_session(context)
        await browser.close()

    return _dedupe_jobs(enriched)


def _needs_enrichment(job: NormalizedJob) -> bool:
    if not job.url or "naukri.com" not in job.url:
        return False
    if not job.salary_text or not parse_salary_lpa(job.salary_text):
        return True
    if (job.description or "").startswith("Keyword search:"):
        return True
    return False


async def _enrich_naukri_detail(page, job: NormalizedJob) -> NormalizedJob:
    await rate_wait("naukri.com")
    await page.goto(job.url, wait_until="domcontentloaded", timeout=25000)
    await page.wait_for_timeout(600)

    salary = job.salary_text
    for sel in (".salary", ".sal", "[class*='salary']", ".compensation", ".ctc"):
        el = await page.query_selector(sel)
        if el:
            text = (await el.inner_text()).strip()
            if text and len(text) < 80:
                salary = text
                break

    description = job.description
    for sel in (".job-desc", ".dang-inner-html", "#jobDescriptionText", "[class*='job-description']"):
        el = await page.query_selector(sel)
        if el:
            text = (await el.inner_text()).strip()
            if len(text) > 80:
                description = text[:8000]
                break

    return NormalizedJob(
        external_id=job.external_id,
        title=job.title,
        company=job.company,
        location=job.location,
        remote=job.remote,
        salary_text=salary,
        description=description,
        url=job.url,
        source=job.source,
        posted_at=job.posted_at,
    )


async def _parse_naukri_card(card, keyword: str) -> NormalizedJob | None:
    try:
        title_el = await card.query_selector("a.title, .title, h2 a, a[title]")
        company_el = await card.query_selector(".companyInfo, .comp-name, .companyName")
        loc_el = await card.query_selector(".locWdth, .location, .loc")
        salary_el = await card.query_selector(".salary, .sal-wrap")

        title = (await title_el.inner_text()).strip() if title_el else None
        if not title:
            return None

        url = await title_el.get_attribute("href") if title_el else None
        company = (await company_el.inner_text()).strip() if company_el else "Unknown"
        location = (await loc_el.inner_text()).strip() if loc_el else None
        salary = (await salary_el.inner_text()).strip() if salary_el else None

        external_id = _extract_id(url or title)
        return NormalizedJob(
            external_id=f"naukri:{external_id}",
            title=title,
            company=company,
            location=location,
            remote="remote" in (location or "").lower() or "wfh" in (location or "").lower(),
            salary_text=salary,
            description=f"Keyword search: {keyword}",
            url=url or f"https://www.naukri.com/{quote_plus(keyword)}-jobs",
            source="naukri",
            posted_at=datetime.utcnow(),
        )
    except Exception:
        return None


def _extract_id(url: str) -> str:
    match = re.search(r"job-listings-(\d+)", url)
    if match:
        return match.group(1)
    return re.sub(r"[^a-zA-Z0-9]", "-", url)[-50:]


def _dedupe_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    seen: set[str] = set()
    result = []
    for job in jobs:
        key = f"{job.source}:{job.external_id}"
        if key not in seen:
            seen.add(key)
            result.append(job)
    return result


def discover_naukri_jobs_sync(**kwargs) -> list[NormalizedJob]:
    return asyncio.run(discover_naukri_jobs(**kwargs))
