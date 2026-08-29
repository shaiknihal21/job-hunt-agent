import operator
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from sqlalchemy.orm import Session

from app.agents.apply.naukri import run_naukri_apply
from app.agents.discovery import run_discovery
from app.agents.ranking import rank_jobs_batch, save_job_score
from app.agents.tailoring import generate_cover_letter, tailor_resume
from app.config import settings
from app.models.profile import Application, Job, Profile, Resume
from app.services.resume.store import application_status_for_result, save_tailored_resume
from app.services.seed import get_or_create_profile


class AgentState(TypedDict):
    profile_id: int
    jobs: list[int]
    pending_approvals: Annotated[list[int], operator.add]
    approved_jobs: Annotated[list[int], operator.add]
    skipped_jobs: Annotated[list[int], operator.add]
    applications: Annotated[list[int], operator.add]
    messages: Annotated[list[str], operator.add]


def load_profile_node(state: AgentState, db: Session) -> AgentState:
    profile = get_or_create_profile(db)
    return {"profile_id": profile.id, "messages": ["Profile loaded"]}


def discover_jobs_node(state: AgentState, db: Session) -> AgentState:
    profile = db.query(Profile).get(state["profile_id"])
    jobs, _ = run_discovery(db, location=profile.location if profile else "Hyderabad")
    return {"jobs": [j.id for j in jobs], "messages": [f"Discovered {len(jobs)} jobs"]}


def rank_jobs_node(state: AgentState, db: Session) -> AgentState:
    profile = db.query(Profile).get(state["profile_id"])
    pending: list[int] = []
    job_objs = [db.query(Job).get(jid) for jid in state.get("jobs", [])]
    job_objs = [j for j in job_objs if j and profile]

    breakdowns = rank_jobs_batch(job_objs, profile)
    for job in job_objs:
        breakdown = breakdowns[job.id]
        save_job_score(db, job, breakdown)

        if breakdown.score >= settings.min_match_score:
            job.status = "pending_approval"
            pending.append(job.id)
            db.commit()
        else:
            job.status = "saved"

    db.commit()
    return {"pending_approvals": pending, "messages": [f"{len(pending)} jobs pending approval"]}


def await_approval_node(state: AgentState, db: Session) -> AgentState:
    approved: list[int] = []
    skipped: list[int] = []

    for job_id in state.get("pending_approvals", []):
        job = db.query(Job).get(job_id)
        if not job or not job.score:
            continue

        decision = interrupt({
            "type": "job_approval",
            "job_id": job_id,
            "title": job.title,
            "company": job.company,
            "score": job.score.score,
            "reasons": job.score.reasons,
            "red_flags": job.score.red_flags,
            "url": job.url,
        })

        if decision.get("decision") == "approve":
            approved.append(job_id)
            job.status = "approved"
        else:
            skipped.append(job_id)
            job.status = "skipped"
        db.commit()

    return {
        "approved_jobs": approved,
        "skipped_jobs": skipped,
        "messages": [f"Approved {len(approved)}, skipped {len(skipped)}"],
    }


def tailor_resume_node(state: AgentState, db: Session) -> AgentState:
    profile = db.query(Profile).get(state["profile_id"])
    master = (
        db.query(Resume)
        .filter(Resume.profile_id == state["profile_id"], Resume.is_master == True)  # noqa: E712
        .first()
    )

    for job_id in state.get("approved_jobs", []):
        job = db.query(Job).get(job_id)
        if not job or not master:
            continue

        result = tailor_resume(profile, master, job)
        cover = generate_cover_letter(profile, job, master.parsed_text or "")

        tailored = save_tailored_resume(db, profile, master, job, result)

        app = Application(
            profile_id=profile.id,
            job_id=job.id,
            resume_id=tailored.id,
            status=application_status_for_result(result),
            cover_letter=cover,
            apply_url=job.url,
            notes="; ".join(result.validation_errors) if result.validation_errors else None,
        )
        db.add(app)

    db.commit()
    return {"messages": ["Resumes tailored for approved jobs"]}


def human_review_submit_node(state: AgentState, db: Session) -> AgentState:
    applications: list[int] = []

    apps = (
        db.query(Application)
        .filter(Application.profile_id == state["profile_id"], Application.status == "pending_submit")
        .all()
    )

    for app in apps:
        job = app.job
        decision = interrupt({
            "type": "submit_approval",
            "application_id": app.id,
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "cover_letter_preview": (app.cover_letter or "")[:500],
        })

        if decision.get("decision") == "approve":
            applications.append(app.id)
            app.status = "submit_approved"
        else:
            app.status = "rejected"
        db.commit()

    return {"applications": applications, "messages": [f"{len(applications)} applications approved for submit"]}


def submit_application_node(state: AgentState, db: Session) -> AgentState:
    profile = db.query(Profile).get(state["profile_id"])
    today_count = (
        db.query(Application)
        .filter(
            Application.profile_id == state["profile_id"],
            Application.applied_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
            Application.status == "applied",
        )
        .count()
    )

    profile_data = {
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "application_defaults": profile.application_defaults,
        "custom_answers": profile.custom_answers or {},
    }

    for app_id in state.get("applications", []):
        if today_count >= settings.max_daily_applications:
            break

        app = db.query(Application).get(app_id)
        if not app or not app.resume:
            continue

        job = app.job
        if job.source == "naukri":
            result = run_naukri_apply(job.url, app.resume.file_path, profile_data, submit=True)
        else:
            result = run_naukri_apply(job.url, app.resume.file_path, profile_data, submit=False)

        app.status = "applied" if result.get("submitted") else "prepared"
        app.confirmation_screenshot = result.get("screenshot")
        if result.get("submitted"):
            app.applied_at = datetime.utcnow()
        job.status = "applied" if result.get("submitted") else "approved"
        today_count += 1
        db.commit()

    return {"messages": ["Applications submitted"]}


def build_workflow(db: Session):
    graph = StateGraph(AgentState)

    graph.add_node("load_profile", lambda s: load_profile_node(s, db))
    graph.add_node("discover", lambda s: discover_jobs_node(s, db))
    graph.add_node("rank", lambda s: rank_jobs_node(s, db))
    graph.add_node("await_approval", lambda s: await_approval_node(s, db))
    graph.add_node("tailor", lambda s: tailor_resume_node(s, db))
    graph.add_node("human_review", lambda s: human_review_submit_node(s, db))
    graph.add_node("submit", lambda s: submit_application_node(s, db))

    graph.set_entry_point("load_profile")
    graph.add_edge("load_profile", "discover")
    graph.add_edge("discover", "rank")
    graph.add_edge("rank", "await_approval")
    graph.add_edge("await_approval", "tailor")
    graph.add_edge("tailor", "human_review")
    graph.add_edge("human_review", "submit")
    graph.add_edge("submit", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory, interrupt_before=["await_approval", "human_review"])


# Singleton compiled graphs per thread
_graphs: dict[str, object] = {}


def get_compiled_graph(db: Session):
    return build_workflow(db)


def start_workflow(db: Session) -> tuple[str, dict]:
    thread_id = str(uuid.uuid4())
    graph = get_compiled_graph(db)
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"jobs": [], "pending_approvals": [], "approved_jobs": [], "skipped_jobs": [], "applications": [], "messages": []}, config)
    return thread_id, result


def resume_workflow(db: Session, thread_id: str, decision: dict) -> dict:
    graph = get_compiled_graph(db)
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(decision, config)
