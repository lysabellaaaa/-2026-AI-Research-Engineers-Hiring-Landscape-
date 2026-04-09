"""Indeed scraper using RSS feeds and public search pages.

Indeed provides RSS for job searches. Playwright fallback for richer data.
"""
from __future__ import annotations

import random
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import feedparser
import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, JobPosting

SEARCH_TERMS = [
    "agents research engineer",
    "AI agents engineer",
    "agentic AI engineer",
    "LLM agents engineer",
    "autonomous agents machine learning",
]

LOCATION = "San Francisco Bay Area, CA"
LOCATION_ENCODED = "San+Francisco+Bay+Area%2C+CA"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

AGENT_KEYWORDS = [
    "agent", "agentic", "langchain", "langgraph", "rag", "tool use",
    "multi-agent", "llm", "large language model", "autonomous",
]


def _is_relevant(title: str, summary: str) -> bool:
    combined = (title + " " + summary).lower()
    return any(kw in combined for kw in AGENT_KEYWORDS)


def _parse_salary_from_summary(summary: str) -> tuple[float | None, float | None]:
    """Quick salary parse from RSS summary text."""
    import re
    # $150K - $200K or $150,000 - $200,000
    patterns = [
        r"\$(\d{1,3})[Kk]\s*[-–]\s*\$?(\d{1,3})[Kk]",
        r"\$(\d{3}),(\d{3})\s*[-–]\s*\$?(\d{3}),(\d{3})",
    ]
    for pat in patterns:
        m = re.search(pat, summary)
        if m:
            g = m.groups()
            if len(g) == 2:
                return float(g[0]) * 1000, float(g[1]) * 1000
    return None, None


class IndeedScraper(BaseScraper):
    source = "indeed"

    def __init__(self, data_dir: Path):
        super().__init__(data_dir)

    def _fetch_rss(self, query: str) -> list[JobPosting]:
        q_encoded = query.replace(" ", "+")
        rss_url = (
            f"https://www.indeed.com/rss?q={q_encoded}"
            f"&l={LOCATION_ENCODED}&fromage=180&radius=25"
        )
        try:
            feed = feedparser.parse(rss_url)
            postings = []
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                company_tag = entry.get("source", {})
                company = company_tag.get("value", "Unknown") if isinstance(company_tag, dict) else "Unknown"
                published = entry.get("published", "")[:10] if entry.get("published") else None

                if not _is_relevant(title, summary):
                    continue

                sal_min, sal_max = _parse_salary_from_summary(summary)

                clean_summary = BeautifulSoup(summary, "lxml").get_text(" ", strip=True)

                postings.append(JobPosting(
                    id=JobPosting.make_id("indeed", link),
                    title=title,
                    company=company,
                    company_type="unknown",
                    location=LOCATION,
                    salary_min=sal_min,
                    salary_max=sal_max,
                    salary_tc_min=None,
                    salary_tc_max=None,
                    experience_years_min=None,
                    experience_years_max=None,
                    skills=[],
                    subfield_tags=[],
                    source="indeed",
                    url=link,
                    raw_text=clean_summary[:3000],
                    scraped_date=date.today().isoformat(),
                    posted_date=published,
                ))
            return postings
        except Exception as e:
            print(f"[Indeed] RSS '{query}' failed: {e}")
            return []

    def _fetch_search_page(self, query: str) -> list[JobPosting]:
        """Scrape Indeed search results page directly."""
        params = {
            "q": query,
            "l": LOCATION,
            "fromage": "180",
            "sort": "date",
        }
        url = f"https://www.indeed.com/jobs?{urlencode(params)}"
        try:
            time.sleep(random.uniform(3, 6))
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            postings = []

            for card in soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard")[:20]:
                title_el = card.select_one("h2.jobTitle span, a.jobtitle")
                company_el = card.select_one("span.companyName, span[data-testid='company-name']")
                link_el = card.select_one("a[href*='/rc/clk'], a[id*='job_']")
                snippet_el = card.select_one("div.job-snippet, div[class*='snippet']")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                href = link_el.get("href", "") if link_el else ""
                link = f"https://www.indeed.com{href}" if href.startswith("/") else href

                if not _is_relevant(title, snippet) or not title:
                    continue

                postings.append(JobPosting(
                    id=JobPosting.make_id("indeed", link or title + company),
                    title=title,
                    company=company,
                    company_type="unknown",
                    location=LOCATION,
                    salary_min=None,
                    salary_max=None,
                    salary_tc_min=None,
                    salary_tc_max=None,
                    experience_years_min=None,
                    experience_years_max=None,
                    skills=[],
                    subfield_tags=[],
                    source="indeed",
                    url=link,
                    raw_text=snippet[:2000],
                    scraped_date=date.today().isoformat(),
                    posted_date=None,
                ))
            return postings
        except Exception as e:
            print(f"[Indeed] Page scrape '{query}' failed: {e}")
            return []

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        seen_ids: set[str] = set()

        for query in SEARCH_TERMS:
            print(f"[Indeed] Searching: '{query}'")
            # Try RSS first (faster, no JS needed)
            rss_results = self._fetch_rss(query)
            for p in rss_results:
                if p.id not in seen_ids:
                    seen_ids.add(p.id)
                    postings.append(p)

            # Also try page scrape for additional results
            page_results = self._fetch_search_page(query)
            for p in page_results:
                if p.id not in seen_ids:
                    seen_ids.add(p.id)
                    postings.append(p)

            time.sleep(random.uniform(4, 7))

        print(f"[Indeed] Total relevant postings: {len(postings)}")
        return postings
