"""Build a screening answer cheatsheet for Naukri assisted apply."""

from app.agents.apply.naukri_screening import answer_for_question


def load_saved_answers(db, profile_id: int) -> dict[str, str]:
    from app.models.profile import ApplicationAnswer

    out: dict[str, str] = {}
    if not db:
        return out
    rows = db.query(ApplicationAnswer).filter(ApplicationAnswer.profile_id == profile_id).all()
    for row in rows:
        key = row.question_text.lower()[:80]
        out[key] = row.answer_text
    return out


def merge_profile_data(profile, db=None) -> dict:
    data = {
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "application_defaults": profile.application_defaults or {},
        "custom_answers": dict(profile.custom_answers or {}),
    }
    if db:
        saved = load_saved_answers(db, profile.id)
        data["custom_answers"].update(saved)
    return data


def build_cheatsheet(profile_data: dict) -> list[str]:
    defaults = profile_data.get("application_defaults") or {}
    years = defaults.get("years_experience", 1)
    lines = [
        f"Years of experience: {years}",
        f"Notice period (days): {defaults.get('notice_period_days', 30)}",
    ]
    if defaults.get("current_ctc"):
        lines.append(f"Current CTC: {defaults['current_ctc']}")
    if defaults.get("expected_ctc"):
        lines.append(f"Expected CTC: {defaults['expected_ctc']}")

    common_questions = [
        "How many years of experience do you have in Retrieval Augmented Generation?",
        "How many years of experience do you have in LLM?",
        "How many years of experience do you have in Python?",
        "How many years of experience do you have in machine learning?",
        "Are you willing to relocate?",
    ]
    for q in common_questions:
        ans = answer_for_question(q, profile_data)
        if ans:
            lines.append(f"{q} → {ans}")

    custom = profile_data.get("custom_answers") or {}
    for k, v in list(custom.items())[:8]:
        lines.append(f"{k} → {v}")

    lines.append("Resume: upload your master PDF from ~/Downloads if the chatbot asks")
    return lines
