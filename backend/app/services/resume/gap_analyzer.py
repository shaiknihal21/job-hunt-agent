from app.services.resume.tech_terms import normalize_term, term_in_text
from app.services.resume.types import CandidateEvidence, GapItem, GapStatus, ParsedJD


RELATED_TERMS: dict[str, list[str]] = {
    "generative ai": ["langchain", "rag", "llm", "gen ai", "genai", "prompt engineering"],
    "gen ai": ["langchain", "rag", "llm", "generative ai", "genai"],
    "genai": ["langchain", "rag", "llm", "generative ai", "gen ai"],
    "llm": ["langchain", "rag", "large language model", "gen ai", "generative ai"],
    "llm apis": ["langchain", "openai api", "rest api", "apis"],
    "vector databases": ["vector database", "embeddings", "rag", "pinecone", "faiss"],
    "vector database": ["embeddings", "rag", "vector databases"],
    "langgraph": ["langchain", "agentic", "agents"],
    "mlops": ["machine learning", "deployment", "ml pipelines", "ci/cd"],
    "kubernetes": ["k8s", "docker", "deployment"],
}


def _has_related_evidence(term: str, evidence: CandidateEvidence, resume_text: str) -> bool:
    for related in RELATED_TERMS.get(normalize_term(term), []):
        if term_in_text(related, resume_text) or any(term_in_text(related, v) for v in evidence.verified_terms):
            return True
    return False


def _status_for_term(term: str, evidence: CandidateEvidence, resume_text: str) -> GapItem:
    norm = normalize_term(term)
    in_profile = any(term_in_text(norm, skill) or term_in_text(skill, norm) for skill in evidence.profile_skills)
    in_resume = term_in_text(norm, resume_text)
    in_verified = any(term_in_text(norm, v) for v in evidence.verified_terms)

    if in_resume and (in_profile or in_verified):
        return GapItem(term=term, status=GapStatus.MATCHED, note="Present in resume and verified evidence")
    if in_resume:
        return GapItem(term=term, status=GapStatus.MATCHED, note="Present in resume text")
    if in_profile or in_verified:
        return GapItem(term=term, status=GapStatus.SUPPORTED_BUT_NOT_EMPHASIZED, note="Supported by profile/evidence but not prominent in resume")
    if _has_related_evidence(term, evidence, resume_text):
        return GapItem(term=term, status=GapStatus.SUPPORTED_BUT_NOT_EMPHASIZED, note="Related verified experience found")
    return GapItem(term=term, status=GapStatus.MISSING, note="Not found in verified candidate evidence")


def analyze_gaps(parsed_jd: ParsedJD, evidence: CandidateEvidence) -> list[GapItem]:
    resume_text = evidence.resume_text.lower()
    terms = sorted(
        set(
            parsed_jd.required_skills
            + parsed_jd.preferred_skills
            + parsed_jd.tools
            + parsed_jd.frameworks
            + parsed_jd.cloud_platforms
            + parsed_jd.languages
            + [kw.term for kw in parsed_jd.keywords if kw.priority.value != "OPTIONAL"]
        )
    )

    report = [_status_for_term(term, evidence, resume_text) for term in terms if term]
    return report


def gaps_to_strengthen(report: list[GapItem]) -> list[str]:
    return [
        item.term
        for item in report
        if item.status in {GapStatus.MATCHED, GapStatus.SUPPORTED_BUT_NOT_EMPHASIZED}
    ]


def verified_strengthen_terms(report: list[GapItem], evidence: CandidateEvidence) -> list[str]:
    terms = []
    for item in report:
        if item.status not in {GapStatus.MATCHED, GapStatus.SUPPORTED_BUT_NOT_EMPHASIZED}:
            continue
        if term_in_text(item.term, evidence.verified_text) or any(
            term_in_text(item.term, skill) for skill in evidence.profile_skills
        ):
            terms.append(item.term)
    return terms


def gaps_missing(report: list[GapItem]) -> list[str]:
    return [item.term for item in report if item.status == GapStatus.MISSING]
