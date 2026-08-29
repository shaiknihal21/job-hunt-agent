from pydantic import BaseModel, Field


class SalaryExpectations(BaseModel):
    min_lpa: float | None = None
    currency: str = "INR"


class ApplicationDefaults(BaseModel):
    notice_period_days: int = 30
    current_ctc: str | None = None
    expected_ctc: str | None = None
    years_experience: int | None = None


class ProfileLinks(BaseModel):
    linkedin: str = ""
    github: str = ""


class ProfileCreate(BaseModel):
    name: str
    role: str
    email: str | None = None
    phone: str | None = None
    location: str
    work_authorization: str = "India"
    skills: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    salary_expectations: SalaryExpectations = Field(default_factory=SalaryExpectations)
    links: ProfileLinks = Field(default_factory=ProfileLinks)
    application_defaults: ApplicationDefaults = Field(default_factory=ApplicationDefaults)
    custom_answers: dict[str, str] = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    work_authorization: str | None = None
    skills: list[str] | None = None
    target_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    salary_expectations: SalaryExpectations | None = None
    links: ProfileLinks | None = None
    application_defaults: ApplicationDefaults | None = None
    custom_answers: dict[str, str] | None = None


class ProfileResponse(ProfileCreate):
    id: int

    model_config = {"from_attributes": True}


class ResumeResponse(BaseModel):
    id: int
    profile_id: int
    job_id: int | None
    is_master: bool
    filename: str
    parsed_text: str | None
    target_role: str | None = None
    ats_score_before: float | None = None
    ats_score_after: float | None = None
    validation_status: str | None = None
    keywords_emphasized: list[str] | None = None

    model_config = {"from_attributes": True}


class JobScoreResponse(BaseModel):
    score: float
    skill_match: float
    experience_match: float
    location_match: float
    salary_match: float
    company_boost: float
    reasons: list[str]
    red_flags: list[str]

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: int
    external_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    salary_text: str | None
    description: str | None
    url: str
    source: str
    status: str
    score: JobScoreResponse | None = None

    model_config = {"from_attributes": True}


class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    profile_id: int
    resume_id: int | None
    status: str
    cover_letter: str | None
    apply_url: str | None
    notes: str | None
    applied_at: str | None = None
    job: JobResponse | None = None

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    decision: str  # approve | skip | reject
    notes: str | None = None
    generate_cover_letter: bool = True


class WeeklyReport(BaseModel):
    period_start: str
    period_end: str
    total_discovered: int
    total_applied: int
    total_interviews: int
    total_rejected: int
    response_rate: float
    top_missed_jobs: list[JobResponse]
