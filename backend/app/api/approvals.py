from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.agents.apply.naukri import run_naukri_apply
from app.agents.graph import resume_workflow, start_workflow
from app.agents.tailoring import generate_cover_letter, tailor_resume
from app.config import settings
from app.database import get_db
from app.models.profile import Application, Job, Resume
from app.schemas import ApprovalDecision, ApplicationResponse, JobResponse
from app.services.resume.store import application_status_for_result, save_tailored_resume
from app.services.screening import save_screening_log
from app.services.seed import get_or_create_profile

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/scan")
def trigger_scan(db: Session = Depends(get_db)):
    thread_id, result = start_workflow(db)
    return {"thread_id": thread_id, "status": "started", "result": result}


@router.get("/queue", response_model=list[JobResponse])
def approval_queue(db: Session = Depends(get_db)):
    jobs = (
        db.query(Job)
        .options(joinedload(Job.score))
        .filter(Job.status == "pending_approval")
        .all()
    )
    return [j for j in jobs if j.score and j.score.score >= settings.min_match_score]


@router.post("/jobs/{job_id}/decide")
def decide_job(job_id: int, decision: ApprovalDecision, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    job = db.query(Job).options(joinedload(Job.score)).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    if decision.decision == "skip":
        job.status = "skipped"
        db.commit()
        return {"status": "skipped", "job_id": job_id}

    if decision.decision != "approve":
        job.status = "rejected"
        db.commit()
        return {"status": "rejected", "job_id": job_id}

    existing = (
        db.query(Application)
        .filter(Application.profile_id == profile.id, Application.job_id == job.id)
        .first()
    )
    if existing:
        raise HTTPException(409, f"Already approved as application #{existing.id}")

    job.status = "approved"
    master = (
        db.query(Resume)
        .filter(Resume.profile_id == profile.id, Resume.is_master == True)  # noqa: E712
        .first()
    )
    if not master:
        raise HTTPException(400, "Upload a master resume first")

    result = tailor_resume(profile, master, job)
    cover = ""
    if decision.generate_cover_letter:
        cover = generate_cover_letter(profile, job, master.parsed_text or "")

    tailored = save_tailored_resume(db, profile, master, job, result)

    app = Application(
        profile_id=profile.id,
        job_id=job.id,
        resume_id=tailored.id,
        status=application_status_for_result(result),
        cover_letter=cover,
        apply_url=job.url,
        notes=decision.notes or ("; ".join(result.validation_errors) if result.validation_errors else None),
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    return {
        "status": "approved",
        "job_id": job_id,
        "application_id": app.id,
        "summary": result.content.summary,
        "resume_path": result.file_path,
        "target_role": result.target_role,
        "ats_before": result.ats_before.overall,
        "ats_after": result.ats_after.overall,
        "validation_status": result.validation_status,
        "validation_errors": result.validation_errors,
        "gaps_missing": result.content.gaps,
        "keywords_emphasized": result.keywords_emphasized,
    }


@router.post("/applications/{application_id}/submit")
def submit_application(application_id: int, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(404, "Application not found")

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
        raise HTTPException(429, f"Daily limit of {settings.max_daily_applications} applications reached")

    resume = db.query(Resume).filter(Resume.id == app.resume_id).first()
    if not resume:
        raise HTTPException(400, "No tailored resume found")

    job = db.query(Job).filter(Job.id == app.job_id).first()
    profile_data = {
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "application_defaults": profile.application_defaults,
        "custom_answers": profile.custom_answers or {},
    }

    result = run_naukri_apply(job.url, resume.file_path, profile_data, submit=True)
    submitted = bool(result.get("submitted"))
    app.status = "applied" if submitted else "prepared"
    app.confirmation_screenshot = result.get("screenshot")
    if submitted:
        app.applied_at = datetime.utcnow()
    screening = result.get("screening_answers") or []
    if screening:
        save_screening_log(db, profile.id, screening)
    job.status = "applied" if submitted else "approved"
    db.commit()

    return {"status": app.status, "application_id": app.id, "result": result}
