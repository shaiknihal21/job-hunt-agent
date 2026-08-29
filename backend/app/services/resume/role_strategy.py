from app.models.profile import Job


ROLE_STRATEGIES: dict[str, dict] = {
    "ai engineer": {
        "emphasis": [
            "python", "artificial intelligence", "apis", "backend", "ai systems",
            "cloud", "data processing", "model integration", "ai application development",
        ],
        "prompt": "Emphasize AI systems, APIs, backend integration, cloud, and model integration using verified evidence only.",
    },
    "genai engineer": {
        "emphasis": [
            "generative ai", "llm", "rag", "embeddings", "vector database", "langchain",
            "langgraph", "prompt engineering", "llm apis", "agentic", "python", "fastapi",
        ],
        "prompt": "Emphasize GenAI, LLMs, RAG, embeddings, vector databases, LangChain/LangGraph, and agentic workflows only when verified.",
    },
    "generative ai engineer": {
        "emphasis": [
            "generative ai", "llm", "rag", "embeddings", "vector database", "langchain",
            "langgraph", "prompt engineering", "python", "fastapi",
        ],
        "prompt": "Emphasize GenAI, LLMs, RAG, embeddings, vector databases, LangChain/LangGraph, and agentic workflows only when verified.",
    },
    "machine learning engineer": {
        "emphasis": [
            "python", "machine learning", "data processing", "model development",
            "model evaluation", "ml pipelines", "apis", "deployment", "cloud", "mlops",
        ],
        "prompt": "Emphasize ML model development, evaluation, pipelines, deployment, cloud, and MLOps using verified evidence only.",
    },
    "ml engineer": {
        "emphasis": [
            "python", "machine learning", "data processing", "model development",
            "model evaluation", "ml pipelines", "apis", "deployment", "cloud", "mlops",
        ],
        "prompt": "Emphasize ML model development, evaluation, pipelines, deployment, cloud, and MLOps using verified evidence only.",
    },
    "software developer": {
        "emphasis": [
            "programming", "software engineering", "apis", "backend", "databases",
            "cloud", "integration", "testing", "git", "ci/cd", "system design",
        ],
        "prompt": "Emphasize software engineering, APIs, backend, databases, cloud, testing, Git, CI/CD, and system design using verified evidence only.",
    },
    "software engineer": {
        "emphasis": [
            "programming", "software engineering", "apis", "backend", "databases",
            "cloud", "integration", "testing", "git", "ci/cd", "system design",
        ],
        "prompt": "Emphasize software engineering, APIs, backend, databases, cloud, testing, Git, CI/CD, and system design using verified evidence only.",
    },
}


DEFAULT_STRATEGY = {
    "emphasis": ["python", "apis", "cloud", "software engineering", "machine learning"],
    "prompt": "Emphasize the strongest verified technical experience relevant to the job description.",
}


SKIP_TERMS = {
    "required", "preferred", "qualifications", "responsibilities", "experience",
    "education", "general", "about", "role", "must", "have", "bonus", "nice",
    "what", "you", "will", "need", "minimum", "essential", "mandatory", "desired",
    "engineer", "developer", "years", "build", "applications",
}


def detect_target_role(job: Job) -> str:
    title = job.title.lower()
    if "gen ai" in title or "genai" in title or "generative ai" in title:
        return "genai engineer"
    if "llm" in title:
        return "genai engineer"
    if "machine learning" in title or title.startswith("ml ") or " ml " in title:
        return "machine learning engineer"
    if "software" in title or "developer" in title or "backend" in title or "full stack" in title:
        return "software engineer"
    for role in sorted(ROLE_STRATEGIES, key=len, reverse=True):
        if role in title:
            return role
    if "ai" in title:
        return "ai engineer"
    return "ai engineer"


def get_role_strategy(job: Job) -> tuple[str, dict]:
    role = detect_target_role(job)
    strategy = ROLE_STRATEGIES.get(role, DEFAULT_STRATEGY)
    return role, strategy
