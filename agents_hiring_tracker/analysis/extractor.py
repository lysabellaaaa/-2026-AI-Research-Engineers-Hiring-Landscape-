"""NLP extraction: salary, experience, skills, subfield tags from raw job text."""
from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Salary patterns
# ---------------------------------------------------------------------------
_SALARY_PATTERNS = [
    # $150K - $200K  or  $150k–$200k
    (r"\$(\d{1,3})[Kk]\s*[-–—]\s*\$?(\d{1,3})[Kk]", "k_range"),
    # $150,000 - $200,000
    (r"\$(\d{1,3}),(\d{3})\s*[-–—]\s*\$?(\d{1,3}),(\d{3})", "full_range"),
    # $150K+
    (r"\$(\d{1,3})[Kk]\+", "k_plus"),
    # up to $200K
    (r"up to \$(\d{1,3})[Kk]", "k_upto"),
    # 150000 to 200000 (bare numbers near salary context)
    (r"\b(\d{3}),(\d{3})\s*(?:to|[-–—])\s*(\d{3}),(\d{3})\b", "bare_full"),
]

def extract_salary(text: str) -> tuple[Optional[float], Optional[float]]:
    """Return (salary_min, salary_max) in USD from free text. Returns (None, None) if not found."""
    for pattern, kind in _SALARY_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        g = m.groups()
        if kind == "k_range":
            return float(g[0]) * 1000, float(g[1]) * 1000
        if kind == "full_range":
            lo = float(g[0]) * 1000 + float(g[1])
            hi = float(g[2]) * 1000 + float(g[3])
            return lo, hi
        if kind == "k_plus":
            v = float(g[0]) * 1000
            return v, v * 1.5
        if kind == "k_upto":
            v = float(g[0]) * 1000
            return None, v
        if kind == "bare_full":
            lo = float(g[0]) * 1000 + float(g[1])
            hi = float(g[2]) * 1000 + float(g[3])
            return lo, hi
    return None, None


# ---------------------------------------------------------------------------
# Experience patterns
# ---------------------------------------------------------------------------
_EXP_PATTERNS = [
    # "5+ years of experience"
    (r"(\d+)\+\s*years?\s+(?:of\s+)?experience", "min_only"),
    # "3-5 years of experience" or "3 to 5 years"
    (r"(\d+)\s*[-–to]\s*(\d+)\s*years?\s+(?:of\s+)?experience", "range"),
    # "minimum 2 years"
    (r"minimum\s+(?:of\s+)?(\d+)\s*years?", "min_only"),
    # "at least 3 years"
    (r"at\s+least\s+(\d+)\s*years?", "min_only"),
    # "X years of" (more generic)
    (r"(\d+)\s*years?\s+of\s+(?:relevant\s+)?(?:professional\s+)?(?:work\s+)?experience", "min_only"),
    # "experience: 2+ years"
    (r"experience[:\s]+(\d+)\+?\s*years?", "min_only"),
]

def extract_experience(text: str) -> tuple[Optional[int], Optional[int]]:
    """Return (years_min, years_max). years_min=0 means truly entry-level/no min stated."""
    for pattern, kind in _EXP_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        g = m.groups()
        if kind == "min_only":
            v = int(g[0])
            return v, None
        if kind == "range":
            return int(g[0]), int(g[1])
    # Explicit "new grad" or "entry level" → 0 years
    if re.search(r"new\s*grad|entry[\s-]level|0[\s-]*year", text, re.IGNORECASE):
        return 0, 2
    return None, None


# ---------------------------------------------------------------------------
# Skills taxonomy (~55 canonical skills)
# ---------------------------------------------------------------------------
_SKILLS = {
    # Languages & frameworks
    "Python": [r"\bpython\b"],
    "PyTorch": [r"\bpytorch\b", r"\btorch\b"],
    "JAX": [r"\bjax\b"],
    "TensorFlow": [r"\btensorflow\b"],
    "Rust": [r"\brust\b"],
    "C++": [r"\bc\+\+\b", r"\bcpp\b"],
    "TypeScript": [r"\btypescript\b"],
    # LLM / Agents frameworks
    "LangChain": [r"\blangchain\b"],
    "LangGraph": [r"\blanggraph\b"],
    "LlamaIndex": [r"\bllamaindex\b", r"\bllama[\s_-]?index\b"],
    "OpenAI API": [r"\bopenai\s+api\b", r"\bgpt-4\b", r"\bgpt4\b"],
    "Claude API": [r"\bclaude\s+api\b", r"\banthropic\s+api\b"],
    "MCP": [r"\bmodel\s+context\s+protocol\b", r"\bmcp\b"],
    "Tool Use": [r"\btool\s+use\b", r"\bfunction\s+call"],
    "RAG": [r"\brag\b", r"\bretrieval[\s-]augmented\b"],
    "ReAct": [r"\breact\b(?!\s+(?:native|js|component))", r"\breasoning\s+and\s+acting\b"],
    "LATS": [r"\blats\b", r"\blanguage\s+agent\s+tree\s+search\b"],
    "Vector DB": [r"\bvector\s+(?:database|db|store)\b", r"\bpinecone\b", r"\bweaviate\b", r"\bchroma\b", r"\bqdrant\b"],
    "Fine-tuning": [r"\bfine[\s-]?tun"],
    "RLHF": [r"\brlhf\b", r"\breinforcement\s+learning\s+from\s+human"],
    "Reinforcement Learning": [r"\breinforcement\s+learning\b", r"\b\brl\b"],
    "Multi-agent": [r"\bmulti[\s-]?agent"],
    "Prompt Engineering": [r"\bprompt\s+engineer"],
    "Context Engineering": [r"\bcontext\s+engineer"],
    "Evals": [r"\bevals?\b", r"\bevaluation\s+framework"],
    "Observability": [r"\bobservability\b", r"\bmonitoring\b"],
    # Infrastructure
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Docker": [r"\bdocker\b"],
    "AWS": [r"\baws\b", r"\bamazon\s+web\s+services\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle\s+cloud\b"],
    "Azure": [r"\bazure\b"],
    "Distributed Systems": [r"\bdistributed\s+systems?\b"],
    "APIs": [r"\brest\s+api\b", r"\bgraphql\b"],
    # ML concepts
    "Transformers": [r"\btransformer\b", r"\battention\s+mechanism\b"],
    "LLM Architecture": [r"\bllm\s+architecture\b", r"\blarge\s+language\s+model\b"],
    "Inference Optimization": [r"\binference\s+optim", r"\blatency\s+optim", r"\bquantiz"],
    "Synthetic Data": [r"\bsynthetic\s+data\b"],
    "Safety/Alignment": [r"\bai\s+safety\b", r"\balignment\b", r"\brlhf\b"],
    # Research skills
    "Paper Writing": [r"\bpaper\b.*\bpublish\b", r"\bpublish.*\bresearch\b", r"\bpeer[\s-]reviewed\b"],
    "Experimentation": [r"\ba/b\s+test\b", r"\bexperiment\s+design\b"],
}

def extract_skills(text: str) -> list[str]:
    """Return list of canonical skill names found in text."""
    found = []
    text_lower = text.lower()
    for skill, patterns in _SKILLS.items():
        if any(re.search(p, text_lower) for p in patterns):
            found.append(skill)
    return found


# ---------------------------------------------------------------------------
# Subfield tagging
# ---------------------------------------------------------------------------
_SUBFIELD_PATTERNS = {
    "agents": [
        r"\bagent\b", r"\bagentic\b", r"\bautonomous\b", r"\borchestrat",
        r"\btool\s+use\b", r"\bmulti[\s-]?agent\b", r"\bplanning\b",
    ],
    "NLP": [
        r"\bnlp\b", r"\bnatural\s+language\b", r"\btext\s+generation\b",
        r"\bsentiment\b", r"\bner\b", r"\bnamed\s+entity\b",
    ],
    "CV": [
        r"\bcomputer\s+vision\b", r"\bcv\b(?!\s+required)", r"\bimage\s+recogni",
        r"\bobject\s+detect\b", r"\bvision[\s-]language\b",
    ],
    "RL": [
        r"\breinforcement\s+learning\b", r"\brl\b", r"\bpolicy\s+gradient\b",
        r"\bppo\b", r"\brlhf\b",
    ],
    "MLOps": [
        r"\bmlops\b", r"\bml\s+platform\b", r"\bmodel\s+deploy",
        r"\bmodel\s+serving\b", r"\bml\s+infrastructure\b",
    ],
    "LLM": [
        r"\blarge\s+language\s+model\b", r"\bllm\b", r"\bgpt\b",
        r"\bfoundation\s+model\b", r"\bpre[\s-]?train",
    ],
}

def extract_subfields(text: str) -> list[str]:
    """Return list of AI subfield tags for a job posting."""
    found = []
    text_lower = text.lower()
    for tag, patterns in _SUBFIELD_PATTERNS.items():
        if any(re.search(p, text_lower) for p in patterns):
            found.append(tag)
    return found if found else ["general_ai"]


# ---------------------------------------------------------------------------
# Apply all extractors to a JobPosting in-place
# ---------------------------------------------------------------------------
def enrich_posting(posting) -> None:
    """Mutate a JobPosting with extracted fields from raw_text."""
    text = posting.raw_text or ""

    if posting.salary_min is None and posting.salary_max is None:
        posting.salary_min, posting.salary_max = extract_salary(text)

    if posting.experience_years_min is None:
        posting.experience_years_min, posting.experience_years_max = extract_experience(text)

    if not posting.skills:
        posting.skills = extract_skills(text)

    if not posting.subfield_tags or posting.subfield_tags == ["agents"]:
        posting.subfield_tags = extract_subfields(text)
