from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"
DATA_DIR = BASE_DIR / "data"
RESUMES_DIR = DATA_DIR / "resumes"
BROWSER_SESSIONS_DIR = DATA_DIR / "browser_sessions"

TARGET_ROLES = [
    "AI Engineer",
    "Gen AI Engineer",
    "Generative AI Engineer",
    "ML Engineer",
    "Machine Learning Engineer",
    "Applied AI Engineer",
    "LLM Engineer",
    "AI/ML Engineer",
    "Software Engineer",
    "Backend Engineer",
    "Full Stack Engineer",
    "Data Engineer",
    "Analytics Engineer",
]

SEARCH_KEYWORDS = [
    "AI Engineer",
    "ML Engineer",
    "Software Engineer",
    "Data Engineer",
    "Backend Engineer",
    "Python Developer",
]

FRESHER_SEARCH_KEYWORDS = [
    "Fresher Software Engineer",
    "Junior AI Engineer",
    "Associate Software Engineer",
    "Entry Level Data Engineer",
    "Graduate Engineer Trainee",
    "Junior Data Engineer",
    "Software Engineer 0 to 2 years",
    "Associate ML Engineer",
]

SEARCH_LOCATIONS = [
    "Hyderabad",
    "Bangalore",
    "Pune",
    "Chennai",
    "Mumbai",
    "Delhi",
    "Noida",
    "Remote",
    "Pan India",
]

FRESHER_POSITIVE_KEYWORDS = [
    "fresher", "entry level", "entry-level", "graduate", "junior", "associate",
    "0-2", "0 - 2", "1-2", "1 - 2", "0 to 2", "1 year", "2 years",
    "early career", "new grad", "trainee", "get", "0-1", "1-3",
]

FRESHER_NEGATIVE_KEYWORDS = [
    "10+ years", "15+ years", "12+ years", "8+ years", "7+ years", "5-8 years",
    "principal", "staff engineer", "director", "vp ", "head of", "architect with 8",
    "senior staff", "distinguished",
]


def get_search_keywords() -> list[str]:
    """Combined role keywords — fresher-friendly first."""
    return list(dict.fromkeys([*FRESHER_SEARCH_KEYWORDS, *SEARCH_KEYWORDS]))


# Extra LinkedIn/Naukri city searches (aggregators — any company, not FAANG-only)
LINKEDIN_LOCATIONS = [
    "India",
    "Hyderabad, Telangana, India",
    "Bengaluru, Karnataka, India",
    "Pune, Maharashtra, India",
    "Chennai, Tamil Nadu, India",
    "Mumbai, Maharashtra, India",
]

# Candidate's home country — on-site abroad roles are excluded unless remote/WFH
HOME_COUNTRY_KEYWORDS = [
    "india", "hyderabad", "bangalore", "bengaluru", "pune", "mumbai", "delhi",
    "ncr", "gurgaon", "gurugram", "chennai", "kolkata", "noida", "remote india",
]

REMOTE_KEYWORDS = [
    "remote", "wfh", "work from home", "work-from-home", "hybrid remote",
    "fully remote", "remote-first", "remote first", "anywhere", "distributed",
    "virtual", "online", "telecommute", "global remote", "work remotely",
]

ABROAD_LOCATION_KEYWORDS = [
    "usa", "u.s.", "united states", "uk", "united kingdom", "europe", "singapore",
    "canada", "australia", "germany", "ireland", "netherlands", "switzerland",
    "san francisco", "seattle", "new york", "london", "toronto", "sydney", "dublin",
    "mountain view", "sunnyvale", "cupertino", "redmond", "austin", "boston",
]

# Well-known product companies — scoring boost only, NOT a filter
PREFERRED_COMPANIES = [
    # Global product MNCs
    "Microsoft",
    "Google",
    "Amazon",
    "NVIDIA",
    "Meta",
    "Apple",
    "Adobe",
    "Salesforce",
    "Oracle",
    "SAP",
    "VMware",
    "Intuit",
    "Uber",
    "LinkedIn",
    "Spotify",
    "Atlassian",
    "ServiceNow",
    "Snowflake",
    "Databricks",
    "OpenAI",
    "Anthropic",
    "Stripe",
    "PayPal",
    "Cisco",
    "Intel",
    "AMD",
    "Qualcomm",
    "Netflix",
    "Airbnb",
    "Twilio",
    "MongoDB",
    "Elastic",
    "Cloudflare",
    "Zscaler",
    "Palo Alto Networks",
    # India product / SaaS companies
    "Flipkart",
    "Swiggy",
    "Razorpay",
    "PhonePe",
    "Freshworks",
    "Zoho",
    "CRED",
    "Meesho",
    "ShareChat",
    "Dream11",
]

# Service-based / IT consulting — excluded from discovery and ranking
EXCLUDED_COMPANIES = [
    "TCS",
    "Tata Consultancy",
    "Infosys",
    "Wipro",
    "HCL",
    "HCLTech",
    "Capgemini",
    "Cognizant",
    "Accenture",
    "Tech Mahindra",
    "LTIMindtree",
    "LTI",
    "Mindtree",
    "Mphasis",
    "Persistent",
    "Cyient",
    "Genpact",
    "Deloitte",
    "IBM Consulting",
    "DXC",
    "Coforge",
    "Hexaware",
    "Zensar",
    "Birlasoft",
]


def is_excluded_company(company: str) -> bool:
    company_lower = company.lower()
    return any(excluded.lower() in company_lower for excluded in EXCLUDED_COMPANIES)


def is_preferred_company(company: str) -> bool:
    """Known product MNC — used for ranking boost, not discovery filter."""
    company_lower = company.lower()
    return any(preferred.lower() in company_lower for preferred in PREFERRED_COMPANIES)


def is_service_company(company: str) -> bool:
    """Heuristic: consulting/staffing firms beyond the explicit blocklist."""
    company_lower = company.lower()
    service_keywords = [
        "consulting", "consultancy", "staffing", "outsourcing",
        "recruitment", "manpower", "bpo", "kpo", "solutions pvt",
    ]
    return any(kw in company_lower for kw in service_keywords)


def is_remote_job(location: str | None, remote: bool = False, description: str | None = None, title: str | None = None) -> bool:
    combined = f"{location or ''} {description or ''} {title or ''}".lower()
    return remote or any(kw in combined for kw in REMOTE_KEYWORDS)


def is_india_location(location: str | None, description: str | None = None) -> bool:
    combined = f"{location or ''} {description or ''}".lower()
    return any(kw in combined for kw in HOME_COUNTRY_KEYWORDS)


def is_abroad_location(location: str | None, description: str | None = None) -> bool:
    combined = f"{location or ''} {description or ''}".lower()
    return any(kw in combined for kw in ABROAD_LOCATION_KEYWORDS)


def is_location_eligible(
    location: str | None,
    remote: bool = False,
    description: str | None = None,
    title: str | None = None,
) -> bool:
    """India on-site/hybrid OK. Outside India only if remote/WFH/online."""
    if is_remote_job(location, remote, description, title):
        return True
    if is_india_location(location, description):
        return True
    if is_abroad_location(location, description):
        return False
    # Ambiguous (e.g. aggregator with no location) — keep for manual review
    return True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_max_tokens: int = 8192

    database_url: str = f"sqlite:///{DATA_DIR / 'jobhunt.db'}"
    min_match_score: int = 55
    auto_apply_min_score: int = 60
    auto_apply_min_ats_score: int = 60
    min_salary_lpa: float = 0.0
    auto_apply_enabled: bool = True
    include_faang_careers: bool = False
    include_linkedin: bool = True
    include_foundit: bool = False
    # Comma-separated sources for auto cycle, or "*" for all
    auto_apply_sources: str = "*"
    auto_apply_allow_needs_review: bool = False
    filter_excluded_companies: bool = False
    # assisted = open browser, you finish apply (reliable). full = Playwright auto-submit (experimental)
    naukri_apply_mode: str = "assisted"
    assisted_apply_wait_sec: int = 180
    candidate_years_experience: int = 1
    max_daily_applications: int = 5
    playwright_headless: bool = False
    scan_interval_hours: int = 24
    discovery_source_timeout_sec: int = 300
    scraper_min_delay_ms: int = 800
    llm_rank_top_n: int = 20
    naukri_enrich_max: int = 40

    notify_telegram_bot_token: str = ""
    notify_telegram_chat_id: str = ""


settings = Settings()


def get_auto_apply_sources() -> set[str] | None:
    """Return allowed sources, or None if all sources are allowed (*)."""
    raw = (settings.auto_apply_sources or "").strip().lower()
    if not raw or raw == "*":
        return None
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def can_auto_submit(source: str) -> bool:
    allowed = get_auto_apply_sources()
    if allowed is None:
        return True
    return source.lower() in allowed


def company_is_blocked(company: str) -> bool:
    """When filter_excluded_companies=true, block IT services/consulting firms."""
    if not settings.filter_excluded_companies:
        return False
    return is_excluded_company(company) or is_service_company(company)


# Ensure data directories exist
RESUMES_DIR.mkdir(parents=True, exist_ok=True)
BROWSER_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
