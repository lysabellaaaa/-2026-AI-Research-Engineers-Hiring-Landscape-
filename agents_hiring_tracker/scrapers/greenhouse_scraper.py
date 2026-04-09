"""Greenhouse/Lever ATS scraper for targeted companies.

Fetches job listings directly from company ATS pages. These are public JSON
endpoints with no anti-scraping measures — most reliable data source.
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, JobPosting

# Companies with their ATS type and board token / URL
# ats_type: "greenhouse" | "lever" | "ashby"
# For lever: just the org slug (e.g. "mistral")
# For ashby: org slug used in jobs.ashbyhq.com/{slug}
COMPANY_TARGETS = [
    # (company_name, ats_type, board_token_or_slug)
    ("Anthropic", "greenhouse", "anthropic"),
    ("Symbolica AI", "greenhouse", "symbolica"),
    ("Cognition AI", "greenhouse", "cognitionlabs"),
    ("Mistral AI", "lever", "mistral"),
    ("METR", "lever", "metr"),
    ("Imbue", "lever", "imbue"),
    ("Cohere", "ashby", "cohere"),
    ("Sierra", "ashby", "Sierra"),
    ("Letta", "ashby", "letta"),
]

# Keywords that flag a role as agents-related
AGENT_TITLE_KEYWORDS = [
    "agent", "agentic", "autonomous", "llm", "language model",
    "research engineer", "ml engineer", "ai engineer",
]

AGENT_DESC_KEYWORDS = [
    "agent", "agentic", "langchain", "langgraph", "rag", "tool use",
    "multi-agent", "reasoning", "planning", "reinforcement learning",
    "mcp", "model context protocol",
]

BAY_AREA_LOCS = [
    "san francisco", "sf", "bay area", "palo alto", "mountain view",
    "menlo park", "redwood city", "berkeley", "remote",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def _is_relevant_title(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in AGENT_TITLE_KEYWORDS)


def _is_bay_area(location: str) -> bool:
    loc = location.lower()
    return any(kw in loc for kw in BAY_AREA_LOCS)


class GreenhouseScraper(BaseScraper):
    source = "greenhouse"

    def __init__(self, data_dir: Path):
        super().__init__(data_dir)

    def _fetch_greenhouse(self, company: str, board_token: str) -> list[dict]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", [])
            print(f"[Greenhouse] {company}: {len(jobs)} total jobs")
            return jobs
        except Exception as e:
            print(f"[Greenhouse] {company} failed: {e}")
            return []

    def _fetch_ashby(self, company: str, slug: str) -> list[dict]:
        """Ashby public job board API."""
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobPostings", [])
            print(f"[Ashby] {company}: {len(jobs)} total jobs")
            return jobs
        except Exception as e:
            print(f"[Ashby] {company} ({slug}) failed: {e}")
            return []

    def _ashby_job_to_posting(self, company: str, job: dict) -> JobPosting | None:
        title = job.get("title", "")
        location = job.get("locationName", "") or job.get("employmentType", "")
        if not _is_relevant_title(title):
            return None

        # Ashby jobs have a descriptionHtml field
        desc_html = job.get("descriptionHtml", "") or ""
        soup = BeautifulSoup(desc_html, "lxml")
        raw_text = soup.get_text(" ", strip=True)[:5000]

        desc_relevant = any(kw in raw_text.lower() for kw in AGENT_DESC_KEYWORDS)
        if not desc_relevant and not _is_relevant_title(title):
            return None

        if location and not _is_bay_area(location) and "remote" not in location.lower():
            return None

        url = job.get("jobUrl", "") or f"https://jobs.ashbyhq.com/{company}/{job.get('id', '')}"
        updated_at = job.get("updatedAt", "")
        posted_date = updated_at[:10] if updated_at else None

        return JobPosting(
            id=JobPosting.make_id("greenhouse", url),
            title=title,
            company=company,
            company_type="unknown",
            location=location or "Bay Area",
            salary_min=None,
            salary_max=None,
            salary_tc_min=None,
            salary_tc_max=None,
            experience_years_min=None,
            experience_years_max=None,
            skills=[],
            subfield_tags=[],
            source="greenhouse",
            url=url,
            raw_text=raw_text,
            scraped_date=date.today().isoformat(),
            posted_date=posted_date,
        )

    def _fetch_lever(self, company: str, base_url: str) -> list[dict]:
        # Lever provides a JSON endpoint at /v0/postings/{slug}?mode=json
        # Accept either a full URL or just the slug
        slug = base_url.rstrip("/").split("/")[-1]
        api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            print(f"[Lever] {company}: {len(data)} total jobs")
            return data
        except Exception as e:
            print(f"[Lever] {company} ({slug}) failed: {e}")
            return []

    def _greenhouse_job_to_posting(self, company: str, job: dict) -> JobPosting | None:
        title = job.get("title", "")
        location_info = job.get("location", {})
        location = location_info.get("name", "") if isinstance(location_info, dict) else str(location_info)

        if not _is_relevant_title(title):
            return None

        # Check description for agent keywords
        content = job.get("content", "") or ""
        soup = BeautifulSoup(content, "lxml")
        raw_text = soup.get_text(" ", strip=True)[:5000]

        desc_relevant = any(kw in raw_text.lower() for kw in AGENT_DESC_KEYWORDS)
        if not desc_relevant and not _is_relevant_title(title):
            return None

        # Location filter (generous — include remote)
        if location and not _is_bay_area(location) and "remote" not in location.lower():
            return None

        url = job.get("absolute_url", "")
        updated_at = job.get("updated_at", "")
        posted_date = updated_at[:10] if updated_at else None

        return JobPosting(
            id=JobPosting.make_id("greenhouse", url),
            title=title,
            company=company,
            company_type="unknown",  # classifier fills this in
            location=location or "Bay Area",
            salary_min=None,
            salary_max=None,
            salary_tc_min=None,
            salary_tc_max=None,
            experience_years_min=None,
            experience_years_max=None,
            skills=[],
            subfield_tags=[],
            source="greenhouse",
            url=url,
            raw_text=raw_text,
            scraped_date=date.today().isoformat(),
            posted_date=posted_date,
        )

    def _lever_job_to_posting(self, company: str, job: dict) -> JobPosting | None:
        title = job.get("text", "")
        categories = job.get("categories", {})
        location = categories.get("location", "") or job.get("workplaceType", "")

        if not _is_relevant_title(title):
            return None

        # Description
        desc_list = job.get("descriptionPlain", "") or ""
        lists_text = " ".join(
            item.get("text", "")
            for lst in job.get("lists", [])
            for item in lst.get("content", [])
            if isinstance(item, dict)
        )
        raw_text = (desc_list + " " + lists_text)[:5000]

        desc_relevant = any(kw in raw_text.lower() for kw in AGENT_DESC_KEYWORDS)
        if not desc_relevant:
            return None

        if location and not _is_bay_area(location) and "remote" not in location.lower():
            return None

        url = job.get("hostedUrl", "")
        created_at = job.get("createdAt")
        posted_date = None
        if created_at:
            from datetime import datetime
            try:
                posted_date = datetime.fromtimestamp(created_at / 1000).date().isoformat()
            except Exception:
                pass

        return JobPosting(
            id=JobPosting.make_id("greenhouse", url),
            title=title,
            company=company,
            company_type="unknown",
            location=location or "Bay Area",
            salary_min=None,
            salary_max=None,
            salary_tc_min=None,
            salary_tc_max=None,
            experience_years_min=None,
            experience_years_max=None,
            skills=[],
            subfield_tags=[],
            source="greenhouse",
            url=url,
            raw_text=raw_text,
            scraped_date=date.today().isoformat(),
            posted_date=posted_date,
        )

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        seen_ids: set[str] = set()

        for company, ats_type, token_or_url in COMPANY_TARGETS:
            print(f"[ATS] Fetching {company} ({ats_type})...")
            try:
                if ats_type == "greenhouse":
                    jobs = self._fetch_greenhouse(company, token_or_url)
                    for job in jobs:
                        p = self._greenhouse_job_to_posting(company, job)
                        if p and p.id not in seen_ids:
                            seen_ids.add(p.id)
                            postings.append(p)
                elif ats_type == "lever":
                    jobs = self._fetch_lever(company, token_or_url)
                    for job in jobs:
                        p = self._lever_job_to_posting(company, job)
                        if p and p.id not in seen_ids:
                            seen_ids.add(p.id)
                            postings.append(p)
                elif ats_type == "ashby":
                    jobs = self._fetch_ashby(company, token_or_url)
                    for job in jobs:
                        p = self._ashby_job_to_posting(company, job)
                        if p and p.id not in seen_ids:
                            seen_ids.add(p.id)
                            postings.append(p)
            except Exception as e:
                print(f"[ATS] {company} error: {e}")
            time.sleep(0.5)

        print(f"[ATS] Total relevant postings: {len(postings)}")
        return postings
