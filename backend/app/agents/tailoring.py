from app.models.profile import Job, Profile, Resume
from app.services.resume.pipeline import tailor_job_resume
from app.services.resume.types import TailorResult


def _cover_letter(profile: Profile, job: Job) -> str:
    skills = ", ".join((profile.skills or [])[:6])
    return (
        f"Dear Hiring Manager,\n\n"
        f"I am applying for the {job.title} role at {job.company}. "
        f"I am a {profile.role} with hands-on experience in {skills}. "
        f"I would welcome the opportunity to contribute to your team.\n\n"
        f"Best regards,\n{profile.name}"
    )


def tailor_resume(profile: Profile, master_resume: Resume, job: Job) -> TailorResult:
    """Run the full ATS resume pipeline and return a structured result."""
    return tailor_job_resume(profile, master_resume, job)


def generate_cover_letter(profile: Profile, job: Job, master_text: str = "") -> str:
    """Simple template cover letter — reliable for auto-apply (no Groq JSON errors)."""
    return _cover_letter(profile, job)
