from dataclasses import dataclass
from datetime import datetime


@dataclass
class NormalizedJob:
    external_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    salary_text: str | None
    description: str | None
    url: str
    source: str
    posted_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "external_id": self.external_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "remote": self.remote,
            "salary_text": self.salary_text,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "posted_at": self.posted_at,
        }
