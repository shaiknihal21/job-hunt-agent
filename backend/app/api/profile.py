from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.config import RESUMES_DIR
from app.database import get_db
from app.models.profile import Profile, Resume
from app.schemas import ProfileCreate, ProfileResponse, ProfileUpdate, ResumeResponse
from app.services.resume_parser import parse_resume
from app.services.seed import get_or_create_profile, seed_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    return profile


@router.post("/seed", response_model=ProfileResponse)
def seed(db: Session = Depends(get_db)):
    return seed_profile(db)


@router.put("", response_model=ProfileResponse)
def update_profile(data: ProfileUpdate, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            if hasattr(value, "model_dump"):
                setattr(profile, field, value.model_dump())
            else:
                setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/resume", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db)
    suffix = file.filename.split(".")[-1].lower() if file.filename else "pdf"
    if suffix not in {"pdf", "docx", "doc", "txt"}:
        raise HTTPException(400, "Supported formats: PDF, DOCX, TXT")

    file_path = RESUMES_DIR / f"master_{profile.id}.{suffix}"
    content = await file.read()
    file_path.write_bytes(content)

    # Mark previous master as non-master
    db.query(Resume).filter(Resume.profile_id == profile.id, Resume.is_master == True).update({"is_master": False})  # noqa: E712

    parsed = parse_resume(str(file_path))
    resume = Resume(
        profile_id=profile.id,
        is_master=True,
        filename=file.filename or file_path.name,
        file_path=str(file_path),
        parsed_text=parsed,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes", response_model=list[ResumeResponse])
def list_resumes(db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    return db.query(Resume).filter(Resume.profile_id == profile.id).all()
