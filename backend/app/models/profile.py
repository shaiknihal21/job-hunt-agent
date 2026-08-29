from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str] = mapped_column(String(200))
    work_authorization: Mapped[str] = mapped_column(String(100), default="India")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    target_roles: Mapped[list] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    salary_expectations: Mapped[dict] = mapped_column(JSON, default=dict)
    links: Mapped[dict] = mapped_column(JSON, default=dict)
    application_defaults: Mapped[dict] = mapped_column(JSON, default=dict)
    custom_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resumes: Mapped[list["Resume"]] = relationship(back_populates="profile")
    applications: Mapped[list["Application"]] = relationship(back_populates="profile")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    master_resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), nullable=True)
    is_master: Mapped[bool] = mapped_column(Boolean, default=False)
    filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(1000))
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ats_score_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    ats_score_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    ats_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gap_report: Mapped[list | None] = mapped_column(JSON, nullable=True)
    keywords_emphasized: Mapped[list | None] = mapped_column(JSON, nullable=True)
    changes_summary: Mapped[list | None] = mapped_column(JSON, nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    validation_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["Profile"] = relationship(back_populates="resumes")
    job: Mapped["Job | None"] = relationship(back_populates="resumes")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    company: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2000))
    source: Mapped[str] = mapped_column(String(100))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="discovered")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    score: Mapped["JobScore | None"] = relationship(back_populates="job", uselist=False)
    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    resumes: Mapped[list["Resume"]] = relationship(back_populates="job")


class JobScore(Base):
    __tablename__ = "job_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    score: Mapped[float] = mapped_column(Float)
    skill_match: Mapped[float] = mapped_column(Float, default=0)
    experience_match: Mapped[float] = mapped_column(Float, default=0)
    location_match: Mapped[float] = mapped_column(Float, default=0)
    salary_match: Mapped[float] = mapped_column(Float, default=0)
    company_boost: Mapped[float] = mapped_column(Float, default=0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    red_flags: Mapped[list] = mapped_column(JSON, default=list)
    ranked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship(back_populates="score")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("profile_id", "job_id", name="uq_profile_job_application"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_approval")
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    confirmation_screenshot: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile: Mapped["Profile"] = relationship(back_populates="applications")
    job: Mapped["Job"] = relationship(back_populates="applications")
    resume: Mapped["Resume | None"] = relationship()


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    question_fingerprint: Mapped[str] = mapped_column(String(500))
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
