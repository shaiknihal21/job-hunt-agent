from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.agents.discovery import run_discovery
from app.agents.ranking import rank_job, rank_jobs_batch, save_job_score
from app.config import settings
from app.database import get_db
from app.models.profile import Job, JobScore
from app.schemas import JobResponse
from app.services.seed import get_or_create_profile

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/discover")
def discover_jobs(db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    jobs, sources = run_discovery(db, location=profile.location)
    breakdowns = rank_jobs_batch(jobs, profile)
    ranked = 0
    for job in jobs:
        save_job_score(db, job, breakdowns[job.id])
        ranked += 1
    return {
        "discovered": len(jobs),
        "ranked": ranked,
        "sources": [{"name": s.name, "count": s.count, "error": s.error} for s in sources],
    }


@router.get("", response_model=list[JobResponse])
def list_jobs(
    min_score: float | None = Query(None),
    status: str | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Job).options(joinedload(Job.score))
    if status:
        query = query.filter(Job.status == status)
    if source:
        query = query.filter(Job.source == source)
    jobs = query.order_by(Job.created_at.desc()).limit(100).all()

    if min_score is not None:
        jobs = [j for j in jobs if j.score and j.score.score >= min_score]
    return jobs


@router.get("/pending-approval", response_model=list[JobResponse])
def pending_approval(db: Session = Depends(get_db)):
    jobs = (
        db.query(Job)
        .options(joinedload(Job.score))
        .filter(Job.status == "pending_approval")
        .all()
    )
    return [j for j in jobs if j.score and j.score.score >= settings.min_match_score]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).options(joinedload(Job.score)).filter(Job.id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    return job


@router.post("/{job_id}/rank")
def rank_single_job(job_id: int, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    breakdown = rank_job(job, profile)
    score = save_job_score(db, job, breakdown)
    if breakdown.score >= settings.min_match_score:
        job.status = "pending_approval"
        db.commit()
    return {"job_id": job_id, "score": score.score, "reasons": score.reasons}
