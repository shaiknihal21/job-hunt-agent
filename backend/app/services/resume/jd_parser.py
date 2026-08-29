import re
from collections import Counter

from app.models.profile import Job
from app.services.resume.tech_terms import TECH_TERMS, normalize_term, term_in_text
from app.services.resume.types import JDKeyword, KeywordPriority, ParsedJD

SKIP_TERMS = {
    "required", "preferred", "qualifications", "responsibilities", "experience",
    "education", "general", "about", "role", "must", "have", "bonus", "nice",
    "what", "you", "will", "need", "minimum", "essential", "mandatory", "desired",
    "engineer", "developer", "years", "build", "applications",
}


REQUIRED_MARKERS = [
    r"must have", r"required", r"requirements", r"qualifications", r"what you.?ll need",
    r"minimum qualifications", r"essential", r"mandatory",
]
PREFERRED_MARKERS = [
    r"nice to have", r"preferred", r"good to have", r"bonus", r"plus", r"desired",
]
RESPONSIBILITY_MARKERS = [
    r"responsibilit", r"what you.?ll do", r"you will", r"key duties", r"about the role",
]
EDUCATION_MARKERS = [r"education", r"degree", r"bachelor", r"master", r"phd", r"b\.?tech", r"b\.?e\."]
EXPERIENCE_MARKERS = [r"experience", r"years of", r"\d+\+?\s*years"]


def _split_sections(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections: dict[str, list[str]] = {"general": []}
    current = "general"
    for line in lines:
        lower = line.lower()
        if any(re.search(marker, lower) for marker in REQUIRED_MARKERS):
            current = "required"
            sections.setdefault(current, [])
            continue
        if any(re.search(marker, lower) for marker in PREFERRED_MARKERS):
            current = "preferred"
            sections.setdefault(current, [])
            continue
        if any(re.search(marker, lower) for marker in RESPONSIBILITY_MARKERS):
            current = "responsibilities"
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(value) for key, value in sections.items()}


def _extract_explicit_required(text: str) -> list[str]:
    required: list[str] = []
    for match in re.finditer(r"(?:required|must have|requirements)\s*:?\s*([^\n]+)", text, re.I):
        chunk = match.group(1)
        chunk = re.split(r"\.\s*(?:preferred|nice to have|good to have)\b", chunk, flags=re.I)[0]
        parts = re.split(r"[,;|/]", chunk)
        for part in parts:
            cleaned = normalize_term(part)
            cleaned = re.sub(r"\s*\.\s*$", "", cleaned)
            if cleaned and cleaned not in SKIP_TERMS and len(cleaned) > 1 and "preferred" not in cleaned:
                required.append(cleaned)
    return sorted(set(required))


def _extract_explicit_preferred(text: str) -> list[str]:
    preferred: list[str] = []
    for match in re.finditer(r"(?:preferred|nice to have|good to have)\s*:?\s*([^\n]+)", text, re.I):
        chunk = match.group(1)
        chunk = re.split(r"\.\s*\d+\+?\s*years", chunk, flags=re.I)[0]
        parts = re.split(r"[,;|/]", chunk)
        for part in parts:
            cleaned = normalize_term(part)
            cleaned = re.sub(r"\s*\.\s*$", "", cleaned)
            if cleaned and cleaned not in SKIP_TERMS and len(cleaned) > 1:
                preferred.append(cleaned)
    return sorted(set(preferred))


def _extract_terms(text: str) -> list[str]:
    found: list[str] = []
    text_lower = text.lower()
    for term in TECH_TERMS:
        if term_in_text(term, text_lower):
            normalized = normalize_term(term)
            if normalized not in SKIP_TERMS:
                found.append(normalized)
    for token in re.findall(r"\b[A-Z][a-zA-Z0-9+#/.-]{1,30}\b", text):
        normalized = normalize_term(token)
        if len(normalized) > 2 and normalized not in SKIP_TERMS:
            found.append(normalized)
    return sorted(set(found))


def _extract_bullets(text: str) -> list[str]:
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^[-•*]\s+", line) or re.match(r"^\d+[.)]\s+", line):
            bullets.append(re.sub(r"^[-•*\d.)]+\s*", "", line).strip())
        elif len(line) > 25 and not line.endswith(":"):
            bullets.append(line)
    return bullets[:20]


def _classify_priority(term: str, required: set[str], preferred: set[str], counts: Counter) -> KeywordPriority:
    norm = normalize_term(term)
    if norm in required:
        return KeywordPriority.CRITICAL
    if norm in preferred:
        return KeywordPriority.IMPORTANT
    if counts[norm] >= 2:
        return KeywordPriority.IMPORTANT
    return KeywordPriority.OPTIONAL


def _categorize(term: str) -> str:
    norm = normalize_term(term)
    if norm in {"python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#", "scala", "kotlin"}:
        return "language"
    if norm in {"aws", "azure", "gcp", "google cloud"}:
        return "cloud"
    if norm in {"fastapi", "flask", "django", "spring boot", "react", "angular", "vue", "langchain", "langgraph", "pytorch", "tensorflow"}:
        return "framework"
    if norm in {"docker", "kubernetes", "k8s", "git", "jenkins", "terraform", "kafka", "redis", "mongodb", "postgresql"}:
        return "tool"
    return "general"


def parse_job_description(job: Job) -> ParsedJD:
    text = f"{job.title}\n{job.description or ''}"
    sections = _split_sections(text)
    required_text = sections.get("required", "") + "\n" + text
    preferred_text = sections.get("preferred", "")
    resp_text = sections.get("responsibilities", text)

    all_terms = _extract_terms(text)
    required_terms = _extract_explicit_required(text) or _extract_terms(required_text)
    preferred_terms = _extract_explicit_preferred(text) or _extract_terms(preferred_text)

    required_set = set(required_terms)
    preferred_set = set(preferred_terms) - required_set

    counts = Counter(all_terms)
    keywords = [
        JDKeyword(
            term=term,
            priority=_classify_priority(term, required_set, preferred_set, counts),
            category=_categorize(term),
        )
        for term in all_terms
    ]

    languages = [t for t in all_terms if _categorize(t) == "language"]
    frameworks = [t for t in all_terms if _categorize(t) == "framework"]
    cloud_platforms = [t for t in all_terms if _categorize(t) == "cloud"]
    tools = [t for t in all_terms if _categorize(t) == "tool"]

    education = []
    for line in text.splitlines():
        lower = line.lower()
        if any(re.search(marker, lower) for marker in EDUCATION_MARKERS):
            education.append(line.strip())

    experience = []
    for line in text.splitlines():
        lower = line.lower()
        if any(re.search(marker, lower) for marker in EXPERIENCE_MARKERS):
            experience.append(line.strip())

    certifications = []
    for line in text.splitlines():
        if re.search(r"certif", line, re.I):
            certifications.append(line.strip())

    return ParsedJD(
        required_skills=sorted(required_set) or sorted(all_terms)[:10],
        preferred_skills=sorted(preferred_set),
        responsibilities=_extract_bullets(resp_text)[:12],
        tools=tools,
        frameworks=frameworks,
        cloud_platforms=cloud_platforms,
        languages=languages,
        education_requirements=education[:5],
        experience_requirements=experience[:5],
        certifications=certifications[:5],
        keywords=keywords,
    )
