"""Autonomous daily job hunt: discover → rank → tailor (ATS) → apply."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.agents.discovery import run_discovery
from app.agents.ranking import rank_jobs_batch, save_job_score
from app.agents.tailoring import generate_cover_letter, tailor_resume
from app.config import can_auto_submit, get_auto_apply_sources, settings
from app.services.salary import salary_meets_minimum
from app.models.profile import Application, Job, Resume
from app.services.resume.store import application_status_for_result, save_tailored_resume
from app.services.runner import submit_application
from app.services.notifier import notify_auto_applied, notify_auto_summary
from app.services.seed import get_or_create_profile

logger = logging.getLogger(__name__)


def _today_applied_count(db: Session, profile_id: int) -> int:
    return (
        db.query(Application)
        .filter(
            Application.profile_id == profile_id,
            Application.applied_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
            Application.status == "applied",
        )
        .count()
    )


def _has_application(db: Session, job_id: int) -> bool:
    return db.query(Application).filter(Application.job_id == job_id).first() is not None


def _retryable_applications(db: Session, profile_id: int) -> list[Application]:
    """Applications that were prepared but not submitted (retry any source)."""
    q = (
        db.query(Application)
        .join(Job)
        .options(joinedload(Application.job))
        .filter(
            Application.profile_id == profile_id,
            Application.status.in_(["prepared", "pending_submit"]),
        )
    )
    allowed = get_auto_apply_sources()
    if allowed is not None:
        q = q.filter(Job.source.in_(allowed))
    return q.order_by(Application.updated_at.desc()).all()


def _eligible_jobs(db: Session, profile_id: int) -> list[Job]:
    jobs = (
        db.query(Job)
        .options(joinedload(Job.score))
        .filter(Job.status.in_(["discovered", "ranked", "auto_queued"]))
        .all()
    )
    eligible = []
    for job in jobs:
        if not can_auto_submit(job.source):
            continue
        if not job.score or job.score.score < settings.auto_apply_min_score:
            continue
        if settings.min_salary_lpa > 0 and salary_meets_minimum(job.salary_text, settings.min_salary_lpa) is False:
            continue
        if _has_application(db, job.id):
            continue
        eligible.append(job)
    eligible.sort(key=lambda j: j.score.score if j.score else 0, reverse=True)
    return eligible


def run_daily_auto_apply(db: Session | None = None) -> dict:
    """
    Full autonomous cycle:
    1. Discover new jobs across all platforms
    2. Rank and keep only score >= auto_apply_min_score (default 60)
    3. Tailor ATS-safe resume per job
    4. Auto-submit when resume passes ATS validation
    """
    own_session = db is None
    db = db or __import__("app.database", fromlist=["SessionLocal"]).SessionLocal()

    summary = {
        "discovered": 0,
        "ranked_above_threshold": 0,
        "tailored": 0,
        "applied": 0,
        "retried": 0,
        "assisted": 0,
        "prepared": 0,
        "needs_review": 0,
        "skipped_daily_limit": 0,
        "errors": [],
    }
    source_lines: list[str] = []

    try:
        profile = get_or_create_profile(db)
        master = (
            db.query(Resume)
            .filter(Resume.profile_id == profile.id, Resume.is_master == True)  # noqa: E712
            .first()
        )
        if not master:
            summary["errors"].append("No master resume uploaded — run: upload ~/resume.pdf")
            return summary

        if not settings.auto_apply_enabled:
            summary["errors"].append("Auto-apply disabled (AUTO_APPLY_ENABLED=false)")
            return summary

        # Step 1 — discover & rank
        jobs, sources = run_discovery(db, location=profile.location)
        summary["discovered"] = len(jobs)
        for s in sources:
            if s.error:
                source_lines.append(f"{s.name}: failed")
            else:
                source_lines.append(f"{s.name}: {s.count}")

        breakdowns = rank_jobs_batch(jobs, profile)
        for job in jobs:
            breakdown = breakdowns[job.id]
            save_job_score(db, job, breakdown)
            if breakdown.score >= settings.auto_apply_min_score:
                job.status = "auto_queued"
                summary["ranked_above_threshold"] += 1
            elif breakdown.score >= settings.min_match_score:
                job.status = "pending_approval"
            db.commit()

        remaining = settings.max_daily_applications - _today_applied_count(db, profile.id)

        # Step 1b — retry failed Naukri submissions before new applies
        summary["retried"] = 0
        for app in _retryable_applications(db, profile.id):
            if remaining <= 0:
                break
            job = app.job
            if not job or not can_auto_submit(job.source):
                continue
            try:
                submit_result = submit_application(db, app.id)
                if submit_result["status"] == "applied":
                    summary["applied"] += 1
                    summary["retried"] += 1
                    remaining -= 1
                    notify_auto_applied(job.title, job.company, job.score.score if job.score else 0)
                elif submit_result["status"] == "awaiting_user":
                    summary["assisted"] += 1
                    summary["retried"] += 1
                else:
                    summary["prepared"] += 1
            except Exception as exc:
                db.rollback()
                summary["errors"].append(f"Retry {job.title} @ {job.company}: {exc}")
                logger.exception("Retry apply failed for application %s", app.id)

        # Step 2 — tailor & apply top matches (skip if daily limit reached)
        if remaining <= 0:
            summary["skipped_daily_limit"] = len(_eligible_jobs(db, profile.id))
            if summary["skipped_daily_limit"]:
                summary["errors"].append(
                    f"Daily apply limit reached ({settings.max_daily_applications}/day) — "
                    f"{summary['skipped_daily_limit']} new jobs skipped"
                )
            notify_auto_summary(summary, source_lines or None)
            return summary

        for job in _eligible_jobs(db, profile.id):
            if remaining <= 0:
                summary["skipped_daily_limit"] += 1
                continue

            try:
                result = tailor_resume(profile, master, job)
            except Exception as exc:
                db.rollback()
                summary["errors"].append(f"{job.title} @ {job.company}: tailor failed — {exc}")
                logger.exception("Tailor failed for job %s", job.id)
                continue

            try:
                cover = generate_cover_letter(profile, job, master.parsed_text or "")
                tailored = save_tailored_resume(db, profile, master, job, result)

                app_status = application_status_for_result(result)
                application = Application(
                    profile_id=profile.id,
                    job_id=job.id,
                    resume_id=tailored.id,
                    status=app_status,
                    cover_letter=cover,
                    apply_url=job.url,
                    notes="; ".join(result.validation_errors) if result.validation_errors else None,
                )
                db.add(application)
                job.status = "approved"
                db.commit()
                db.refresh(application)
                summary["tailored"] += 1

                ats_ok = result.ats_after.overall >= settings.auto_apply_min_ats_score
                ready = (
                    result.validation_status == "application_ready"
                    or (settings.auto_apply_allow_needs_review and ats_ok)
                )

                if not ready:
                    application.status = "needs_review"
                    job.status = "needs_review"
                    db.commit()
                    summary["needs_review"] += 1
                    logger.info(
                        "Needs review: %s @ %s (score=%.0f, ATS=%.0f)",
                        job.title, job.company, job.score.score, result.ats_after.overall,
                    )
                    continue

                # Step 3 — auto-submit
                submit_result = submit_application(db, application.id)
                if submit_result["status"] == "applied":
                    summary["applied"] += 1
                    remaining -= 1
                    notify_auto_applied(job.title, job.company, job.score.score if job.score else 0)
                elif submit_result["status"] == "awaiting_user":
                    summary["assisted"] += 1
                    logger.info("Assisted apply (browser): %s @ %s — run track when done", job.title, job.company)
                else:
                    summary["prepared"] += 1
                    logger.info("Prepared (manual submit): %s @ %s", job.title, job.company)

            except Exception as exc:
                db.rollback()
                summary["errors"].append(f"{job.title} @ {job.company}: {exc}")
                logger.exception("Auto-apply failed for job %s", job.id)

    finally:
        if own_session:
            db.close()

    notify_auto_summary(summary, source_lines or None)
    return summary


def format_auto_summary(summary: dict) -> str:
    lines = [
        f"Discovered: {summary['discovered']}",
        f"Score ≥ {settings.auto_apply_min_score}: {summary['ranked_above_threshold']}",
        f"Tailored: {summary['tailored']}",
        f"Applied: {summary['applied']}",
        f"Assisted (browser open): {summary.get('assisted', 0)}",
        f"Retried: {summary.get('retried', 0)}",
        f"Prepared (manual): {summary['prepared']}",
        f"Needs review: {summary['needs_review']}",
    ]
    if summary["skipped_daily_limit"]:
        lines.append(f"Skipped (daily limit): {summary['skipped_daily_limit']}")
    if summary["errors"]:
        lines.append("Errors: " + "; ".join(summary["errors"][:3]))
    return "\n".join(lines)
