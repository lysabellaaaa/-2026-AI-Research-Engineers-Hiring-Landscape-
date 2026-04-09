"""Reddit scraper for informal survey and community sentiment.

Uses the Reddit public JSON API (no auth required for read-only searches).
Falls back to PRAW if credentials are configured in environment.

Collects posts and comments about AI agents roles, salary discussions,
and hiring sentiment — classified as "informal survey" data, not job postings.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from .base import BaseScraper, JobPosting

SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "cscareerquestions",
    "artificial",
    "singularity",
    "learnmachinelearning",
]

SEARCH_QUERIES = [
    "agents research engineer salary",
    "agentic AI jobs bay area",
    "AI agents engineer hiring",
    "LLM agents engineer salary san francisco",
    "agents vs machine learning jobs",
    "AI agents job market 2025",
]

RELEVANCE_KEYWORDS = [
    "agent", "agentic", "langchain", "llm agents", "autonomous agent",
    "research engineer", "bay area", "san francisco", "salary",
]

HEADERS = {
    "User-Agent": "AgentsHiringTracker/1.0 (research tool; contact: research@example.com)"
}


def _unix_to_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).date().isoformat()


def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in RELEVANCE_KEYWORDS)


def _post_to_posting(post: dict, subreddit: str) -> JobPosting | None:
    """Convert a Reddit post dict to a JobPosting (informal survey entry)."""
    data = post.get("data", post)
    title = data.get("title", "")
    selftext = data.get("selftext", "") or ""
    url = f"https://reddit.com{data.get('permalink', '')}"
    created_utc = data.get("created_utc", 0)
    score = data.get("score", 0)

    full_text = f"{title} {selftext}"
    if not _is_relevant(full_text):
        return None

    # Keep high-signal posts (score > 5 or explicit job/salary content)
    salary_words = ["salary", "compensation", "tc", "total comp", "$", "k/yr"]
    has_salary = any(w in full_text.lower() for w in salary_words)
    if score < 3 and not has_salary:
        return None

    cutoff = (date.today() - timedelta(days=60)).isoformat()
    posted_date = _unix_to_date(created_utc) if created_utc else None
    if posted_date and posted_date < cutoff:
        return None

    return JobPosting(
        id=JobPosting.make_id("reddit", url),
        title=f"[Reddit/{subreddit}] {title[:120]}",
        company=f"r/{subreddit}",
        company_type="unknown",
        location="Online / Bay Area discussion",
        salary_min=None,
        salary_max=None,
        salary_tc_min=None,
        salary_tc_max=None,
        experience_years_min=None,
        experience_years_max=None,
        skills=[],
        subfield_tags=["community_sentiment"],
        source="reddit",
        url=url,
        raw_text=full_text[:3000],
        scraped_date=date.today().isoformat(),
        posted_date=posted_date,
    )


class RedditScraper(BaseScraper):
    source = "reddit"

    def __init__(self, data_dir: Path, lookback_days: int = 60):
        super().__init__(data_dir)
        self.lookback_days = lookback_days
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _search_subreddit(self, subreddit: str, query: str) -> list[dict]:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "sort": "relevance",
            "t": "month",
            "limit": 50,
            "restrict_sr": 1,
        }
        try:
            resp = self.session.get(url, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("children", [])
        except Exception as e:
            print(f"[Reddit] r/{subreddit} '{query}' failed: {e}")
            return []

    def _search_global(self, query: str) -> list[dict]:
        url = "https://www.reddit.com/search.json"
        params = {
            "q": query,
            "sort": "relevance",
            "t": "month",
            "limit": 50,
        }
        try:
            resp = self.session.get(url, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("children", [])
        except Exception as e:
            print(f"[Reddit] global search '{query}' failed: {e}")
            return []

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        seen_ids: set[str] = set()

        print("[Reddit] Searching subreddits...")
        for query in SEARCH_QUERIES:
            # Global search
            results = self._search_global(query)
            for post in results:
                p = _post_to_posting(post, "all")
                if p and p.id not in seen_ids:
                    seen_ids.add(p.id)
                    postings.append(p)
            time.sleep(1.5)  # Reddit rate limit: ~60 req/min unauthenticated

        for sub in SUBREDDITS:
            for query in SEARCH_QUERIES[:3]:  # Limit per-subreddit queries
                results = self._search_subreddit(sub, query)
                for post in results:
                    p = _post_to_posting(post, sub)
                    if p and p.id not in seen_ids:
                        seen_ids.add(p.id)
                        postings.append(p)
                time.sleep(1.5)

        print(f"[Reddit] Total relevant posts: {len(postings)}")
        return postings
