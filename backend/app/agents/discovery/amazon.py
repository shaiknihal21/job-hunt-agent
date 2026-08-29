from datetime import datetime

import httpx

from app.agents.discovery.base import NormalizedJob
from app.config import get_search_keywords


AMAZON_JOBS_API = "https://www.amazon.jobs/en/search.json"


async def discover_amazon_jobs(keywords: list[str] | None = None) -> list[NormalizedJob]:
    keywords = keywords or get_search_keywords()[:5]
    all_jobs: list[NormalizedJob] = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for keyword in keywords:
            try:
                response = await client.get(
                    AMAZON_JOBS_API,
                    params={"base_query": keyword, "loc_query": "India", "country": "IND"},
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip, deflate",
                    },
                )
                if response.status_code != 200:
                    continue
                for item in response.json().get("jobs", []):
                    job = _parse_amazon_item(item, keyword)
                    if job:
                        all_jobs.append(job)
            except Exception:
                continue

    return _dedupe_jobs(all_jobs)


def _parse_amazon_item(item: dict, keyword: str) -> NormalizedJob | None:
    try:
        title = item.get("title") or item.get("job_title")
        if not title:
            return None

        job_id = str(item.get("id") or item.get("id_icims") or title)
        city = item.get("city") or ""
        country = item.get("country_code") or "IN"
        location = f"{city}, {country}".strip(", ") or "India"
        description = item.get("description_short") or item.get("description") or f"Amazon role: {keyword}"
        url = item.get("job_path") or f"https://www.amazon.jobs/en/jobs/{job_id}"
        if url.startswith("/"):
            url = f"https://www.amazon.jobs{url}"

        return NormalizedJob(
            external_id=f"amazon:{job_id}",
            title=title.strip(),
            company="Amazon",
            location=location,
            remote="remote" in str(location).lower(),
            salary_text=None,
            description=str(description)[:5000],
            url=url,
            source="amazon",
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
