"""Company type classifier.

Assigns each company one of:
  frontier_lab | ai_safety | big_tech | startup | unknown
"""
from __future__ import annotations

import re

# Exact / near-exact company name sets (lowercase)
FRONTIER_LABS: set[str] = {
    "openai", "anthropic", "google deepmind", "deepmind", "meta ai",
    "meta superintelligence", "meta superintelligence lab", "msl",
    "xai", "x.ai", "mistral", "mistral ai", "inflection ai",
    "cohere", "01.ai", "zhipu ai", "moonshot ai",
}

AI_SAFETY_ORGS: set[str] = {
    "metr", "redwood research", "arc", "alignment research center",
    "apollo research", "constellation", "miri",
    "machine intelligence research institute", "far ai", "far.ai",
    "center for ai safety", "cais", "palisade research",
    "uk ai security institute", "aisi",
}

BIG_TECH: set[str] = {
    "google", "microsoft", "amazon", "apple", "meta", "nvidia",
    "salesforce", "ibm", "intel", "qualcomm", "amd",
    "oracle", "adobe", "servicenow", "palantir",
    "twitter", "x corp", "snap", "lyft", "uber", "airbnb",
    "stripe", "square", "block", "paypal",
}

# Keyword fragments that strongly signal each category
_FRONTIER_FRAGMENTS = [
    "openai", "anthropic", "deepmind", "mistral", "cohere", "xai", "inflection",
]
_SAFETY_FRAGMENTS = [
    "metr", "redwood", "apollo research", "alignment research", "ai safety",
    "far ai", "palisade", "constellation institute",
]
_BIGTECH_FRAGMENTS = [
    "google", "microsoft", "amazon web", "aws", "apple inc", "nvidia",
    "salesforce", "ibm research", "intel labs",
]


def _normalize(name: str) -> str:
    return re.sub(r"[,\.]+", "", name.lower()).strip()


def classify_company(company_name: str) -> str:
    """Return company type string for a given company name."""
    norm = _normalize(company_name)

    # Exact match first
    if norm in FRONTIER_LABS:
        return "frontier_lab"
    if norm in AI_SAFETY_ORGS:
        return "ai_safety"
    if norm in BIG_TECH:
        return "big_tech"

    # Fragment match
    for frag in _FRONTIER_FRAGMENTS:
        if frag in norm:
            return "frontier_lab"
    for frag in _SAFETY_FRAGMENTS:
        if frag in norm:
            return "ai_safety"
    for frag in _BIGTECH_FRAGMENTS:
        if frag in norm:
            return "big_tech"

    # Reddit posts → not a company
    if norm.startswith("r/"):
        return "unknown"

    # Default: startup
    return "startup"


def enrich_company_type(posting) -> None:
    """Mutate posting.company_type in-place."""
    if posting.company_type in ("unknown", "", None):
        posting.company_type = classify_company(posting.company)
