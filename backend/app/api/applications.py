from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.profile import Application, Job
from app.schemas import ApplicationResponse, WeeklyReport
from app.services.seed import get_or_create_profile

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationResponse])
def list_applications(db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    apps = (
        db.query(Application)
        .options(joinedload(Application.job).joinedload(Job.score))
        .filter(Application.profile_id == profile.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return apps


@router.patch("/{application_id}/status")
def update_status(application_id: int, status: str, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    valid = {"pending_approval", "pending_submit", "applied", "interview", "rejected", "offer", "prepared"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Use: {valid}")
    app.status = status
    db.commit()
    return {"application_id": application_id, "status": status}


@router.get("/report/weekly", response_model=WeeklyReport)
def weekly_report(db: Session = Depends(get_db)):
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

    missed = (
        db.query(Job)
        .options(joinedload(Job.score))
        .filter(Job.status == "skipped", Job.created_at >= start)
        .order_by(Job.created_at.desc())
        .limit(5)
        .all()
    )
    missed = sorted(missed, key=lambda j: j.score.score if j.score else 0, reverse=True)

    response_rate = (interviews / applied * 100) if applied else 0.0

    return WeeklyReport(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        total_discovered=discovered,
        total_applied=applied,
        total_interviews=interviews,
        total_rejected=rejected,
        response_rate=round(response_rate, 1),
        top_missed_jobs=missed,
    )
