"""Known technical terms for heuristic JD/resume parsing."""

TECH_TERMS = [
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#", "scala", "kotlin",
    "artificial intelligence", "machine learning", "deep learning", "generative ai", "gen ai", "genai",
    "llm", "large language model", "nlp", "natural language processing", "computer vision",
    "rag", "retrieval augmented generation", "embeddings", "vector database", "vector db",
    "langchain", "langgraph", "prompt engineering", "fine-tuning", "fine tuning", "transformers",
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn", "pandas", "numpy",
    "fastapi", "flask", "django", "spring boot", "node.js", "nodejs", "react", "angular", "vue",
    "rest api", "restful", "graphql", "grpc", "microservices", "backend", "full stack", "fullstack",
    "software engineering", "system design", "data structures", "algorithms",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "dynamodb", "cassandra",
    "kafka", "spark", "airflow", "dbt", "etl", "data pipeline", "data processing",
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s", "terraform",
    "ci/cd", "cicd", "jenkins", "github actions", "git", "mlops", "model deployment",
    "pinecone", "weaviate", "chromadb", "faiss", "huggingface", "openai api", "anthropic",
    "agentic", "agents", "multi-agent", "api integration", "cloud", "devops",
    "testing", "unit testing", "pytest", "integration testing",
    "bachelor", "master", "phd", "b.tech", "b.e.", "m.tech", "computer science",
]

TERM_ALIASES: dict[str, list[str]] = {
    "python": ["python3", "py"],
    "machine learning": ["ml", "machine-learning"],
    "generative ai": ["gen ai", "genai", "generative-ai"],
    "large language model": ["llm", "llms"],
    "kubernetes": ["k8s"],
    "amazon web services": ["aws"],
    "google cloud platform": ["gcp", "google cloud"],
    "microsoft azure": ["azure"],
    "retrieval augmented generation": ["rag"],
    "continuous integration": ["ci/cd", "cicd"],
    "rest api": ["restful", "rest apis", "apis"],
    "fastapi": ["fast api"],
    "langchain": ["lang chain"],
    "langgraph": ["lang graph"],
    "vector database": ["vector db", "vector databases"],
    "prompt engineering": ["prompting"],
    "software engineer": ["software developer", "software development"],
    "backend": ["back-end", "back end"],
    "full stack": ["fullstack", "full-stack"],
}


def normalize_term(term: str) -> str:
    return " ".join(term.lower().strip().split())


def expand_aliases(term: str) -> set[str]:
    base = normalize_term(term)
    variants = {base}
    for canonical, aliases in TERM_ALIASES.items():
        if base == canonical or base in aliases:
            variants.add(canonical)
            variants.update(aliases)
    return variants


def term_in_text(term: str, text: str) -> bool:
    text_lower = text.lower()
    for variant in expand_aliases(term):
        if variant in text_lower:
            return True
    return False
