"""Unified agent actions — used by CLI and API."""

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.agents.apply.careers_assist import CAREERS_SOURCES, careers_assist_mode
from app.agents.apply.naukri import linkedin_assist_mode, run_naukri_apply, run_naukri_assist
from app.agents.discovery import SourceResult, run_discovery
from app.agents.ranking import rank_jobs_batch, save_job_score
from app.agents.tailoring import generate_cover_letter, tailor_resume
from app.config import RESUMES_DIR, settings
from app.models.profile import Application, Job, Profile, Resume
from app.services.resume.store import application_status_for_result, save_tailored_resume
from app.services.resume_parser import parse_resume
from app.services.salary import format_salary_check
from app.services.notifier import notify_pending_jobs
from app.services.apply_assist import merge_profile_data
from app.services.screening import save_screening_log
from app.services.upload_paths import resolve_upload_path
from app.services.seed import get_or_create_profile


def _format_source_stats(sources: list[SourceResult]) -> list[str]:
    lines = []
    for s in sources:
        if s.error:
            lines.append(f"  {s.name}: failed ({s.error})")
        else:
            lines.append(f"  {s.name}: {s.count} jobs ({s.duration_sec:.0f}s)")
    return lines


def format_source_stats_dict(sources: list[dict]) -> list[str]:
    lines = []
    for s in sources:
        if s.get("error"):
            lines.append(f"  {s['name']}: failed ({s['error']})")
        else:
            dur = s.get("duration_sec", 0)
            lines.append(f"  {s['name']}: {s.get('count', 0)} jobs ({dur:.0f}s)")
    return lines


def scan_jobs(db: Session, *, on_progress=None) -> dict:
    profile = get_or_create_profile(db)

    def _progress(name, status, count, error):
        if on_progress:
            on_progress(name, status, count, error)
        elif status == "started":
            print(f"  → {name}...", flush=True)
        elif status == "done":
            print(f"  ✓ {name}: {count} jobs", flush=True)
        elif status == "failed":
            print(f"  ✗ {name}: {error}", flush=True)

    jobs, sources = run_discovery(db, location=profile.location, on_progress=_progress)
    breakdowns = rank_jobs_batch(jobs, profile)
    pending = 0
    for job in jobs:
        breakdown = breakdowns[job.id]
        save_job_score(db, job, breakdown)
        if breakdown.score >= settings.min_match_score:
            job.status = "pending_approval"
            pending += 1
        db.commit()

    pending_jobs = list_pending(db)
    notify_pending_jobs(pending_jobs)

    return {
        "discovered": len(jobs),
        "pending_approval": pending,
        "sources": [{"name": s.name, "count": s.count, "error": s.error, "duration_sec": s.duration_sec} for s in sources],
    }


def list_pending(db: Session) -> list[Job]:
    jobs = (
        db.query(Job)
        .options(joinedload(Job.score))
        .filter(Job.status == "pending_approval")
        .order_by(Job.created_at.desc())
        .all()
    )
    return [j for j in jobs if j.score and j.score.score >= settings.min_match_score]


def list_applications(db: Session) -> list[Application]:
    profile = get_or_create_profile(db)
    return (
        db.query(Application)
        .options(joinedload(Application.job).joinedload(Job.score))
        .filter(Application.profile_id == profile.id)
        .order_by(Application.created_at.desc())
        .all()
    )


def find_job(db: Session, job_id: int | None = None, company_hint: str | None = None) -> Job | None:
    if job_id:
        return db.query(Job).options(joinedload(Job.score)).filter(Job.id == job_id).first()

    if company_hint:
        hint = company_hint.lower()
        for job in list_pending(db):
            if hint in job.company.lower() or hint in job.title.lower():
                return job
    return None


def approve_job(db: Session, job_id: int) -> dict:
    profile = get_or_create_profile(db)
    job = db.query(Job).options(joinedload(Job.score)).filter(Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job #{job_id} not found")

    if job.status in ("applied", "skipped"):
        raise ValueError(f"Job #{job_id} is already {job.status}")

    existing = (
        db.query(Application)
        .filter(Application.profile_id == profile.id, Application.job_id == job.id)
        .first()
    )
    if existing:
        raise ValueError(
            f"Already approved as Application #{existing.id} ({existing.status}). "
            f"Use: apply #{existing.id}"
        )

    master = (
        db.query(Resume)
        .filter(Resume.profile_id == profile.id, Resume.is_master == True)  # noqa: E712
        .first()
    )
    if not master:
        raise ValueError("Upload a resume first: upload /path/to/resume.pdf")

    job.status = "approved"
    result = tailor_resume(profile, master, job)
    cover = generate_cover_letter(profile, job, master.parsed_text or "")

    tailored = save_tailored_resume(db, profile, master, job, result)

    application = Application(
        profile_id=profile.id,
        job_id=job.id,
        resume_id=tailored.id,
        status=application_status_for_result(result),
        cover_letter=cover,
        apply_url=job.url,
        notes="; ".join(result.validation_errors) if result.validation_errors else None,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    return {
        "job_id": job_id,
        "application_id": application.id,
        "title": job.title,
        "company": job.company,
        "summary": result.content.summary,
        "resume_path": result.file_path,
        "pdf_path": str(Path(result.file_path).with_suffix(".pdf")),
        "target_role": result.target_role,
        "ats_before": result.ats_before.overall,
        "ats_after": result.ats_after.overall,
        "validation_status": result.validation_status,
        "gaps_missing": result.content.gaps,
        "keywords_emphasized": result.keywords_emphasized,
    }


def skip_job(db: Session, job_id: int) -> dict:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job #{job_id} not found")
    job.status = "skipped"
    db.commit()
    return {"job_id": job_id, "title": job.title, "company": job.company}


def submit_application(db: Session, application_id: int) -> dict:
    profile = get_or_create_profile(db)
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise ValueError(f"Application #{application_id} not found")

    today_count = (
        db.query(Application)
        .filter(
            Application.profile_id == profile.id,
            Application.applied_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
            Application.status == "applied",
        )
        .count()
    )
    if today_count >= settings.max_daily_applications:
        raise ValueError(f"Daily limit reached ({settings.max_daily_applications}/day)")

    resume = db.query(Resume).filter(Resume.id == application.resume_id).first()
    if not resume:
        raise ValueError("No tailored resume found")

    job = db.query(Job).filter(Job.id == application.job_id).first()
    profile_data = merge_profile_data(profile, db)

    use_full_naukri = settings.naukri_apply_mode.lower() == "full"

    if job.source == "naukri":
        from app.services.browser_session import apply_resume_path
        resume_file = apply_resume_path(resume.file_path)
        if use_full_naukri:
            result = run_naukri_apply(job.url, resume_file, profile_data, submit=True)
        else:
            result = run_naukri_assist(job.url, resume_file, profile_data)
    elif job.source == "linkedin":
        import asyncio
        from app.services.browser_session import apply_resume_path
        result = asyncio.run(linkedin_assist_mode(job.url, apply_resume_path(resume.file_path), profile_data))
    elif job.source in CAREERS_SOURCES:
        import asyncio
        from app.services.browser_session import apply_resume_path
        resume_file = apply_resume_path(resume.file_path)
        result = asyncio.run(careers_assist_mode(job.url, resume_file, profile_data))
    else:
        import asyncio
        from app.services.browser_session import apply_resume_path
        resume_file = apply_resume_path(resume.file_path)
        result = asyncio.run(careers_assist_mode(job.url, resume_file, profile_data))

    submitted = bool(result.get("submitted"))
    if submitted:
        application.status = "applied"
    elif result.get("status") == "awaiting_user" or result.get("mode", "").endswith("_assist"):
        application.status = "awaiting_user"
    else:
        application.status = "prepared"
    application.confirmation_screenshot = result.get("screenshot")
    if submitted:
        application.applied_at = datetime.utcnow()
    screening = result.get("screening_answers") or []
    if screening:
        save_screening_log(db, profile.id, screening)
        note = "; ".join(screening[:5])
        application.notes = (application.notes + " | " + note) if application.notes else note
    job.status = "applied" if submitted else "approved"
    db.commit()

    return {
        "application_id": application_id,
        "status": application.status,
        "title": job.title,
        "company": job.company,
        "result": result,
    }


def upload_resume(db: Session, file_path: str) -> dict:
    profile = get_or_create_profile(db)
    path = resolve_upload_path(file_path)

    suffix = path.suffix.lstrip(".").lower()
    if suffix not in {"pdf", "docx", "doc", "txt"}:
        raise ValueError("Supported formats: PDF, DOCX, TXT")

    dest = RESUMES_DIR / f"master_{profile.id}.{suffix}"
    dest.write_bytes(path.read_bytes())

    db.query(Resume).filter(
        Resume.profile_id == profile.id, Resume.is_master == True  # noqa: E712
    ).update({"is_master": False})

    parsed = parse_resume(str(dest))
    if len(parsed or "") < 100:
        raise ValueError(
            f"Resume parsed only {len(parsed or '')} chars — file may be scanned/image PDF. "
            "Try a text-based PDF or DOCX."
        )
    resume = Resume(
        profile_id=profile.id,
        is_master=True,
        filename=path.name,
        file_path=str(dest),
        parsed_text=parsed,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return {"filename": resume.filename, "chars_parsed": len(parsed or "")}


def update_application_status(db: Session, application_id: int, status: str) -> dict:
    valid = {"pending_approval", "pending_submit", "applied", "interview", "rejected", "offer", "prepared", "needs_review", "awaiting_user"}
    if status not in valid:
        raise ValueError(f"Invalid status. Use one of: {', '.join(sorted(valid))}")

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise ValueError(f"Application #{application_id} not found")

    application.status = status
    db.commit()
    job = db.query(Job).filter(Job.id == application.job_id).first()
    return {
        "application_id": application_id,
        "status": status,
        "title": job.title if job else "—",
        "company": job.company if job else "—",
    }


def weekly_status(db: Session) -> dict:
    profile = get_or_create_profile(db)
    end = datetime.utcnow()
    start = end - timedelta(days=7)

    apps = (
        db.query(Application)
        .filter(Application.profile_id == profile.id, Application.created_at >= start)
        .all()
    )
    discovered = db.query(Job).filter(Job.created_at >= start).count()
    applied = sum(1 for a in apps if a.status == "applied")
    interviews = sum(1 for a in apps if a.status == "interview")
    rejected = sum(1 for a in apps if a.status == "rejected")
    offers = sum(1 for a in apps if a.status == "offer")
    pending = len(list_pending(db))
    all_apps = (
        db.query(Application)
        .filter(Application.profile_id == profile.id)
        .all()
    )
    ready = sum(1 for a in all_apps if a.status in ("pending_submit", "prepared", "awaiting_user"))
    needs_review = sum(1 for a in all_apps if a.status == "needs_review")

    return {
        "discovered_7d": discovered,
        "applied_7d": applied,
        "interviews_7d": interviews,
        "rejected_7d": rejected,
        "offers_7d": offers,
        "pending_approval": pending,
        "ready_to_submit": ready,
        "needs_review": needs_review,
        "response_rate": round((interviews / applied * 100) if applied else 0, 1),
    }


def format_job(job: Job) -> str:
    score = job.score.score if job.score else 0
    loc = job.location or ("Remote" if job.remote else "—")
    reason = job.score.reasons[0] if job.score and job.score.reasons else ""
    sal = format_salary_check(job.salary_text, settings.min_salary_lpa)
    return f"#{job.id}  {score:.0f}%  {job.title} @ {job.company} ({loc}) · {sal} — {reason}"


def format_application(app: Application) -> str:
    job = app.job
    title = job.title if job else "—"
    company = job.company if job else "—"
    return f"#{app.id}  [{app.status}]  {title} @ {company}"
