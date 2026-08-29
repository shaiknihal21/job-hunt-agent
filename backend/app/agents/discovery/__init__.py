import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.discovery.base import NormalizedJob
from app.agents.discovery.amazon import discover_amazon_jobs
from app.agents.discovery.linkedin import discover_linkedin_jobs
from app.agents.discovery.microsoft import (
    discover_foundit_jobs,
    discover_google_jobs,
    discover_microsoft_jobs,
    discover_nvidia_jobs,
)
from app.agents.discovery.naukri import discover_naukri_jobs
from app.config import get_search_keywords, company_is_blocked, is_location_eligible, settings
from app.services.salary import is_salary_eligible
from app.models.profile import Job

ProgressCallback = Callable[[str, str, int | None, str | None], None]


@dataclass
class SourceResult:
    name: str
    count: int = 0
    error: str | None = None
    duration_sec: float = 0.0


@dataclass
class DiscoveryResult:
    jobs: list[NormalizedJob] = field(default_factory=list)
    sources: list[SourceResult] = field(default_factory=list)


async def discover_all_jobs(
    keywords: list[str] | None = None,
    location: str = "Hyderabad",
    *,
    on_progress: ProgressCallback | None = None,
) -> DiscoveryResult:
    """
    Primary sources: Naukri + LinkedIn (parallel, with per-source timeout).
    Foundit/FAANG are optional and fail fast when blocked.
    """
    keywords = keywords or get_search_keywords()
    timeout = float(settings.discovery_source_timeout_sec)

    primary = [("naukri", discover_naukri_jobs(keywords, location))]
    if settings.include_linkedin:
        primary.append(("linkedin", discover_linkedin_jobs(keywords)))
    optional: list[tuple[str, asyncio.Future]] = []
    if settings.include_foundit:
        optional.append(("foundit", discover_foundit_jobs(keywords)))
    if settings.include_faang_careers:
        optional.extend([
            ("amazon", discover_amazon_jobs(keywords)),
            ("microsoft", discover_microsoft_jobs(keywords)),
            ("google", discover_google_jobs(keywords)),
            ("nvidia", discover_nvidia_jobs(keywords)),
        ])

    async def _wrap(name: str, coro):
        if on_progress:
            on_progress(name, "started", None, None)
        start = time.monotonic()
        try:
            jobs = await asyncio.wait_for(coro, timeout=timeout)
            meta = SourceResult(name=name, count=len(jobs), duration_sec=time.monotonic() - start)
            if on_progress:
                on_progress(name, "done", len(jobs), None)
            return jobs, meta
        except asyncio.TimeoutError:
            meta = SourceResult(name=name, error=f"timeout ({timeout:.0f}s)", duration_sec=time.monotonic() - start)
            if on_progress:
                on_progress(name, "failed", 0, meta.error)
            return [], meta
        except Exception as exc:
            meta = SourceResult(name=name, error=str(exc)[:120], duration_sec=time.monotonic() - start)
            if on_progress:
                on_progress(name, "failed", 0, meta.error)
            return [], meta

    wrapped = await asyncio.gather(*(_wrap(name, coro) for name, coro in primary))
    all_jobs: list[NormalizedJob] = []
    sources: list[SourceResult] = []
    for (jobs, meta) in wrapped:
        all_jobs.extend(jobs)
        sources.append(meta)

    if optional:
        opt_timeout = min(timeout, 45.0)
        opt_wrapped = await asyncio.gather(
            *(_wrap(name, coro) for name, coro in optional),
            return_exceptions=False,
        )
        for jobs, meta in opt_wrapped:
            if meta.error:
                meta.duration_sec = min(meta.duration_sec, opt_timeout)
            all_jobs.extend(jobs)
            sources.append(meta)

    filtered = _filter_location(_filter_blocked_companies(_dedupe(all_jobs)))
    return DiscoveryResult(jobs=filtered, sources=sources)


def _filter_location(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    return [
        job for job in jobs
        if is_location_eligible(job.location, job.remote, job.description, job.title)
    ]


def _filter_blocked_companies(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    if not settings.filter_excluded_companies:
        return jobs
    return [job for job in jobs if not company_is_blocked(job.company)]


def save_jobs(db: Session, jobs: list[NormalizedJob]) -> list[Job]:
    saved: list[Job] = []
    for nj in jobs:
        if company_is_blocked(nj.company):
            continue
        if not is_location_eligible(nj.location, nj.remote, nj.description, nj.title):
            continue
        if not is_salary_eligible(nj.salary_text, settings.min_salary_lpa):
            continue

        existing = (
            db.query(Job)
            .filter(Job.source == nj.source, Job.external_id == nj.external_id)
            .first()
        )
        if existing:
            updated = False
            if nj.salary_text and (not existing.salary_text or existing.salary_text != nj.salary_text):
                existing.salary_text = nj.salary_text
                updated = True
            if nj.description and len(nj.description) > len(existing.description or ""):
                existing.description = nj.description
                updated = True
            if updated:
                db.commit()
            saved.append(existing)
            continue

        job = Job(
            external_id=nj.external_id,
            title=nj.title,
            company=nj.company,
            location=nj.location,
            remote=nj.remote,
            salary_text=nj.salary_text,
            description=nj.description,
            url=nj.url,
            source=nj.source,
            posted_at=nj.posted_at or datetime.utcnow(),
            status="discovered",
        )
        db.add(job)
        saved.append(job)

    db.commit()
    for job in saved:
        db.refresh(job)
    return saved


def _dedupe(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    seen: set[str] = set()
    out: list[NormalizedJob] = []
    for j in jobs:
        key = f"{j.source}:{j.external_id}"
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


def run_discovery(
    db: Session,
    keywords: list[str] | None = None,
    location: str = "Hyderabad",
    *,
    on_progress: ProgressCallback | None = None,
) -> tuple[list[Job], list[SourceResult]]:
    result = asyncio.run(discover_all_jobs(keywords, location, on_progress=on_progress))
    saved = save_jobs(db, result.jobs)
    return saved, result.sources
