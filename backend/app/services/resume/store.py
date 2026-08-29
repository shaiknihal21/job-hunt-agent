from pathlib import Path

from sqlalchemy.orm import Session

from app.models.profile import Job, Profile, Resume
from app.services.resume.types import TailorResult


def save_tailored_resume(
    db: Session,
    profile: Profile,
    master: Resume,
    job: Job,
    result: TailorResult,
) -> Resume:
    tailored = Resume(
        profile_id=profile.id,
        job_id=job.id,
        master_resume_id=master.id,
        is_master=False,
        filename=Path(result.file_path).name,
        file_path=result.file_path,
        target_role=result.target_role,
        ats_score_before=result.ats_before.overall,
        ats_score_after=result.ats_after.overall,
        ats_breakdown={
            "before": result.ats_before.model_dump(),
            "after": result.ats_after.model_dump(),
        },
        gap_report=[item.model_dump() for item in result.gap_report],
        keywords_emphasized=result.keywords_emphasized,
        changes_summary=result.changes_summary,
        validation_status=result.validation_status,
        validation_errors=result.validation_errors,
    )
    db.add(tailored)
    db.flush()
    return tailored


def application_status_for_result(result: TailorResult) -> str:
    return "pending_submit" if result.validation_status == "application_ready" else "needs_review"
