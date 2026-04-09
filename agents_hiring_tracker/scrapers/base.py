"""Base scraper ABC and shared JobPosting dataclass."""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional


@dataclass
class JobPosting:
    id: str
    title: str
    company: str
    company_type: str          # frontier_lab | ai_safety | startup | big_tech | unknown
    location: str
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_tc_min: Optional[float]
    salary_tc_max: Optional[float]
    experience_years_min: Optional[int]
    experience_years_max: Optional[int]
    skills: list[str]
    subfield_tags: list[str]   # agents | NLP | CV | RL | MLOps | ...
    source: str                # hn | reddit | indeed | greenhouse | glassdoor
    url: str
    raw_text: str
    scraped_date: str          # ISO date string
    posted_date: Optional[str]
    is_new: bool = False

    @staticmethod
    def make_id(source: str, url: str) -> str:
        return hashlib.sha256(f"{source}:{url}".encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)


class BaseScraper(ABC):
    source: str = ""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.raw_dir = data_dir / "raw" / self.source
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def fetch(self) -> list[JobPosting]:
        """Fetch and return list of JobPosting objects."""
        ...

    def save_raw(self, postings: list[JobPosting]) -> Path:
        today = date.today().isoformat()
        out = self.raw_dir / f"{today}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in postings], f, indent=2, default=str)
        return out

    def run(self) -> list[JobPosting]:
        postings = self.fetch()
        self.save_raw(postings)
        return postings
