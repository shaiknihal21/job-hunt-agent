from enum import Enum

from pydantic import BaseModel, Field


class KeywordPriority(str, Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    OPTIONAL = "OPTIONAL"


class GapStatus(str, Enum):
    MATCHED = "MATCHED"
    SUPPORTED_BUT_NOT_EMPHASIZED = "SUPPORTED_BUT_NOT_EMPHASIZED"
    MISSING = "MISSING"
    UNVERIFIED = "UNVERIFIED"


class JDKeyword(BaseModel):
    term: str
    priority: KeywordPriority = KeywordPriority.IMPORTANT
    category: str = "general"


class ParsedJD(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    cloud_platforms: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    keywords: list[JDKeyword] = Field(default_factory=list)


class CandidateEvidence(BaseModel):
    name: str
    role: str
    profile_skills: list[str] = Field(default_factory=list)
    resume_text: str = ""
    verified_terms: list[str] = Field(default_factory=list)
    verified_text: str = ""


class GapItem(BaseModel):
    term: str
    status: GapStatus
    note: str = ""


class ATSBreakdown(BaseModel):
    overall: float = 0.0
    required_skill_coverage: float = 0.0
    preferred_skill_coverage: float = 0.0
    responsibility_alignment: float = 0.0
    experience_alignment: float = 0.0
    education_alignment: float = 0.0
    keyword_coverage: float = 0.0
    role_alignment: float = 0.0


class TailoredContent(BaseModel):
    summary: str = Field(description="Concise job-specific professional summary")
    skills_reordered: list[str] = Field(description="Skills reordered by relevance, verified only")
    experience_bullets: list[str] = Field(description="Rephrased bullets from verified experience only")
    projects: list[str] = Field(default_factory=list, description="Relevant projects from verified experience")
    gaps: list[str] = Field(default_factory=list, description="Missing JD skills not in candidate evidence")


class TailorResult(BaseModel):
    content: TailoredContent
    file_path: str
    target_role: str
    gap_report: list[GapItem] = Field(default_factory=list)
    ats_before: ATSBreakdown = Field(default_factory=ATSBreakdown)
    ats_after: ATSBreakdown = Field(default_factory=ATSBreakdown)
    keywords_emphasized: list[str] = Field(default_factory=list)
    changes_summary: list[str] = Field(default_factory=list)
    validation_status: str = "draft"
    validation_errors: list[str] = Field(default_factory=list)
    fact_check_passed: bool = False
    fact_check_issues: list[str] = Field(default_factory=list)
