"""HackerNews scraper using the free Algolia API.

Fetches 'Who is Hiring?' monthly threads and searches for agent-related roles
in the Bay Area. No authentication required, 10k req/hour limit.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import requests

from .base import BaseScraper, JobPosting

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"

# Search terms for job-related posts
JOB_QUERIES = [
    "agents research engineer",
    "AI agents engineer bay area",
    "agentic AI engineer san francisco",
    "LLM agents research",
    "autonomous agents engineer",
]

# Filter keywords — post must contain at least one
RELEVANCE_KEYWORDS = [
    "agent", "agentic", "autonomous", "llm", "langchain", "langgraph",
    "rag", "tool use", "multi-agent", "reasoning", "planning",
]

BAY_AREA_KEYWORDS = [
    "san francisco", "sf", "bay area", "palo alto", "mountain view",
    "menlo park", "redwood city", "berkeley", "remote",
]


class HNScraper(BaseScraper):
    source = "hn"

    def __init__(self, data_dir: Path, lookback_days: int = 180):
        super().__init__(data_dir)
        self.lookback_days = lookback_days

    def _search_algolia(self, query: str, tags: str = "comment", page: int = 0) -> dict:
        from datetime import datetime
        cutoff_date = date.today() - timedelta(days=self.lookback_days)
        cutoff = int(datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day).timestamp())
        params = {
            "query": query,
            "tags": tags,
            "numericFilters": f"created_at_i>{cutoff}",
            "hitsPerPage": 100,
            "page": page,
        }
        resp = requests.get(f"{ALGOLIA_BASE}/search", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _get_who_is_hiring_threads(self) -> list[dict]:
        """Fetch the last 6 months of 'Who is Hiring?' story IDs."""
        result = self._search_algolia(
            "Ask HN: Who is hiring?", tags="story", page=0
        )
        threads = []
        for hit in result.get("hits", []):
            title = hit.get("title", "")
            if "who is hiring" in title.lower():
                threads.append(hit)
        return threads[:6]  # Up to 6 monthly threads

    def _fetch_thread_comments(self, story_id: str) -> list[dict]:
        """Get all comments from a hiring thread."""
        params = {
            "tags": f"comment,story_{story_id}",
            "hitsPerPage": 1000,
        }
        resp = requests.get(f"{ALGOLIA_BASE}/search", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("hits", [])

    def _is_relevant(self, text: str) -> bool:
        text_lower = text.lower()
        has_agent_keyword = any(kw in text_lower for kw in RELEVANCE_KEYWORDS)
        has_bay_area = any(kw in text_lower for kw in BAY_AREA_KEYWORDS)
        return has_agent_keyword and has_bay_area

    def _comment_to_posting(self, hit: dict) -> JobPosting | None:
        text = hit.get("comment_text") or hit.get("story_text") or ""
        # Strip HTML tags simply
        import re
        text_clean = re.sub(r"<[^>]+>", " ", text).strip()

        if not self._is_relevant(text_clean):
            return None

        # Try to extract company from first line
        lines = [l.strip() for l in text_clean.split("\n") if l.strip()]
        company = lines[0][:80] if lines else "Unknown"
        # Clean pipe-separated formats like "Acme | SF | Full-time"
        if "|" in company:
            company = company.split("|")[0].strip()

        url = hit.get("story_url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        job_id = JobPosting.make_id("hn", url + hit.get("objectID", ""))

        posted_ts = hit.get("created_at")
        posted_date = posted_ts[:10] if posted_ts else None

        return JobPosting(
            id=job_id,
            title="Agents/AI Engineer (HN Listing)",
            company=company,
            company_type="unknown",
            location="Bay Area / Remote",
            salary_min=None,
            salary_max=None,
            salary_tc_min=None,
            salary_tc_max=None,
            experience_years_min=None,
            experience_years_max=None,
            skills=[],
            subfield_tags=["agents"],
            source="hn",
            url=url,
            raw_text=text_clean[:4000],
            scraped_date=date.today().isoformat(),
            posted_date=posted_date,
        )

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        seen_ids: set[str] = set()

        print("[HN] Fetching Who is Hiring? threads...")
        threads = self._get_who_is_hiring_threads()
        print(f"[HN] Found {len(threads)} hiring threads")

        for thread in threads:
            story_id = thread.get("objectID") or thread.get("story_id", "")
            print(f"[HN] Fetching comments for thread {story_id}...")
            comments = self._fetch_thread_comments(str(story_id))
            time.sleep(0.5)

            for hit in comments:
                posting = self._comment_to_posting(hit)
                if posting and posting.id not in seen_ids:
                    seen_ids.add(posting.id)
                    postings.append(posting)

        # Also run direct Algolia searches
        print("[HN] Running direct Algolia job searches...")
        for query in JOB_QUERIES:
            try:
                result = self._search_algolia(query, tags="comment")
                for hit in result.get("hits", []):
                    posting = self._comment_to_posting(hit)
                    if posting and posting.id not in seen_ids:
                        seen_ids.add(posting.id)
                        postings.append(posting)
                time.sleep(0.3)
            except Exception as e:
                print(f"[HN] Query '{query}' failed: {e}")

        print(f"[HN] Total relevant postings found: {len(postings)}")
        return postings
