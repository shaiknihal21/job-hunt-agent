"""Groq LLM client — free tier. No OpenAI/Azure keys required."""

from langchain_openai import ChatOpenAI

from app.config import settings


def get_groq_llm(*, temperature: float = 0.2, max_tokens: int | None = None) -> ChatOpenAI | None:
    """Return a Groq chat model, or None if GROQ_API_KEY is not set."""
    if not settings.groq_api_key:
        return None
    tokens = max_tokens if max_tokens is not None else settings.groq_max_tokens
    return ChatOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=temperature,
        max_tokens=tokens,
    )


def llm_status() -> str:
    if settings.groq_api_key:
        return f"Groq ({settings.groq_model})"
    return "off — heuristic scoring & rule-based tailoring only (set GROQ_API_KEY for AI ranking/tailoring)"
