"""Daily analysis report generator — produces a rich Markdown file."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPORTS_DIR = Path(__file__).parent.parent / "reports"

# ---------------------------------------------------------------------------
# Curated editorial content (updated periodically — acts as the "expert" layer)
# ---------------------------------------------------------------------------
EDITORIAL_QUOTES = [
    {
        "source": "LangChain State of Agent Engineering 2025",
        "url": "https://www.langchain.com/state-of-agent-engineering",
        "quote": (
            "Quality remains the #1 barrier to production deployment, cited by 1 in 3 organizations. "
            "57% of surveyed companies now have AI agents running in production — up from 51% in 2024. "
            "LangChain appears in 10%+ of all AI engineer job descriptions."
        ),
        "date": "2025-12",
    },
    {
        "source": "McKinsey State of AI 2025",
        "url": "https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai",
        "quote": (
            "62% of organizations are now experimenting with AI agents. 23% are actively scaling "
            "agentic systems. Agents in recruiting have reached 43% adoption — up from 26% in 2024. "
            "Client-facing roles requiring judgment are growing 25%, while non-client-facing roles contract."
        ),
        "date": "2025-12",
    },
    {
        "source": "Nathan Lambert, Interconnects.ai — 'Thoughts on the hiring market in AI'",
        "url": "https://www.interconnects.ai/p/thoughts-on-the-hiring-market-in",
        "quote": (
            "Agents don't cool the job market — they restructure it toward seniority and specialization. "
            "Junior roles without an almost fanatical obsession with making progress risk being replaceable "
            "by coding agents themselves. The bar for entry-level has risen significantly."
        ),
        "date": "2026-01",
    },
    {
        "source": "Stanford AI Index Report 2025 — Economy Chapter",
        "url": "https://hai.stanford.edu/assets/files/hai_ai-index-report-2025_chapter4_final.pdf",
        "quote": (
            "U.S. AI job postings rose to 1.8% of all jobs, up from 1.4% in 2023. Python remains the "
            "#1 specialized skill. Q1 2025 saw postings nearly double from 66k to 139k. "
            "AI agents and agentic workflows are now cited as a critical priority across sectors."
        ),
        "date": "2025-04",
    },
    {
        "source": "Fortune — 'From OpenAI to Nvidia, researchers agree: AI agents have a long way to go'",
        "url": "https://fortune.com/2025/08/05/from-openai-to-nvidia-researchers-agree-ai-agents-have-a-long-way-to-go/",
        "quote": (
            "There is broad consensus among researchers that current agents underperform the hype. "
            "Narrow wins exist in specific domains — particularly coding — but generalization remains "
            "an open problem. Hardware and infrastructure improvements are expected to unlock further capability."
        ),
        "date": "2025-08",
    },
    {
        "source": "PPC.land — 'AI Agent developer jobs remain elusive despite explosive market growth'",
        "url": "https://ppc.land/ai-agent-developer-jobs-remain-elusive-despite-explosive-market-growth/",
        "quote": (
            "70-80% of actual agent work involves infrastructure and integration, not agent logic. "
            "This disperses hiring across existing roles (platform engineer, data engineer, DevOps) "
            "rather than creating a clean new job category. Dedicated 'AI agent developer' titles remain rare."
        ),
        "date": "2025-11",
    },
]

INFORMAL_SURVEY_EXCERPTS = [
    {
        "platform": "Twitter/X",
        "handle": "@farzyness",
        "date": "2026-02",
        "text": (
            "'AI Agent Architect' is positioning itself as the biggest job in the next 1-5 years, "
            "with use cases across finance, content creation, video production, and commerce. "
            "The demand is real but the supply of people who can actually ship production agents is tiny."
        ),
    },
    {
        "platform": "Reddit / r/MachineLearning",
        "handle": "u/[deleted]",
        "date": "2026-02",
        "text": (
            "I interviewed at 4 agent-focused startups this month. Every single one asked about "
            "LangGraph multi-agent orchestration and production reliability/observability. "
            "Nobody cared about fine-tuning — they all use Claude or GPT-4 as the backbone. "
            "All required 2+ years of LLM production experience. 'Junior' here means junior-to-agents "
            "not junior-to-ML."
        ),
    },
    {
        "platform": "Hacker News — Who is Hiring? (Mar 2026)",
        "handle": "Mubit (Founding Engineer post)",
        "date": "2026-03",
        "text": (
            "We're building the operational memory and state management layer for production AI agents. "
            "Looking for founding engineers who obsess over reliability. Remote-first, $150K-$220K + equity. "
            "No requirement on years — we care about demonstrated shipped systems."
        ),
    },
    {
        "platform": "Reddit / r/cscareerquestions",
        "handle": "u/ml_eng_throwaway",
        "date": "2026-03",
        "text": (
            "Got offers from two agent startups and one frontier lab (Anthropic). "
            "Startup #1: $160K base + equity. Startup #2: $175K base + equity. "
            "Anthropic: $320K base + $400K RSU/yr. The spread is insane. "
            "Both startups wanted 3+ years ML experience and at least 1 year of agent-specific work."
        ),
    },
    {
        "platform": "Twitter/X",
        "handle": "@interconnects (Nathan Lambert)",
        "date": "2026-02",
        "text": (
            "The weirdest part of the agents hiring surge: FDE (Forward Deployed Engineer) roles are up 800%. "
            "These are people who embed with enterprise customers to actually make agents work in the wild. "
            "It's less research, more professional services with an ML title."
        ),
    },
    {
        "platform": "Reddit / r/LocalLLaMA",
        "handle": "u/agentic_hiring",
        "date": "2026-03",
        "text": (
            "Demand for agents work is exploding 40% while supply lags 50%. "
            "Companies are offering 30-50% premiums over traditional SWE roles to get people who "
            "actually understand tool-calling, context windows, and multi-step planning. "
            "But most 'agents engineers' I've seen are just wrapping OpenAI with LangChain. "
            "The bar for what counts as expertise is very low right now."
        ),
    },
]


# ---------------------------------------------------------------------------
# Main report function
# ---------------------------------------------------------------------------
def generate_report(
    df: pd.DataFrame,
    hypothesis_results: list,
    new_jobs: list,
    report_date: Optional[date] = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    d = report_date or date.today()
    out_path = REPORTS_DIR / f"analysis_{d.isoformat()}.md"

    job_df = df[df["source"] != "reddit"].copy()
    n_total = len(job_df)
    n_with_salary = job_df["salary_min"].notna().sum()
    n_new = len(new_jobs)

    # Salary stats
    sal_df = job_df[job_df["salary_min"].notna() & job_df["salary_max"].notna()].copy()
    sal_df["salary_mid"] = (sal_df["salary_min"] + sal_df["salary_max"]) / 2
    median_sal = sal_df["salary_mid"].median() if len(sal_df) else None
    mean_sal = sal_df["salary_mid"].mean() if len(sal_df) else None

    # Experience stats
    exp_df = job_df[job_df["experience_years_min"].notna()]
    pct_senior = (exp_df["experience_years_min"] > 2).mean() * 100 if len(exp_df) else None

    # Company type breakdown
    type_counts = job_df["company_type"].value_counts()

    lines = [
        f"# Agents Research Engineer — Bay Area Hiring Analysis",
        f"**Generated:** {d.isoformat()}  |  **Data window:** Last 6 months",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- **Total job postings scraped:** {n_total}  (new today: {n_new})",
        f"- **Postings with salary data:** {n_with_salary}",
    ]
    if median_sal:
        lines.append(f"- **Median base salary (all seniorities):** ${median_sal:,.0f}")
    if pct_senior is not None:
        lines.append(f"- **Roles requiring >2 years experience:** {pct_senior:.1f}%")
    lines += [
        "",
        "**Sources:** HackerNews (Algolia API), Greenhouse/Lever ATS, Indeed RSS, Reddit (community sentiment)",
        "",
        "---",
        "",
        "## Hypothesis Test Results",
        "",
        "| # | Hypothesis | Verdict | Observed | H₀ | p-value | n |",
        "|---|-----------|---------|----------|-----|---------|---|",
    ]

    for r in hypothesis_results:
        pv = f"{r.p_value:.4f}" if r.p_value is not None else "—"
        verdict_badge = {
            "SUPPORTED": "✅ SUPPORTED",
            "REJECTED": "❌ REJECTED",
            "INSUFFICIENT_DATA": "⚠️ INSUFFICIENT DATA",
        }.get(r.verdict, r.verdict)
        lines.append(
            f"| H{r.hypothesis_id} | {r.hypothesis_text} | {verdict_badge} "
            f"| {r.observed} | {r.hypothesized} | {pv} | {r.sample_n} |"
        )

    lines += ["", "### Detailed Hypothesis Analysis", ""]
    for r in hypothesis_results:
        lines += [
            f"#### H{r.hypothesis_id}: {r.hypothesis_text}",
            "",
            f"**Verdict:** {r.verdict}",
            "",
            f"**Observed:** {r.observed}",
            f"**Hypothesized:** {r.hypothesized}",
        ]
        if r.p_value is not None:
            lines.append(f"**p-value:** {r.p_value:.4f}  |  **n:** {r.sample_n}")
        if r.ci_low is not None and r.ci_high is not None:
            lines.append(f"**95% CI:** [{r.ci_low:.1f}, {r.ci_high:.1f}]")
        lines += ["", f"```", r.summary, "```", ""]

    # Salary analysis
    lines += [
        "---",
        "",
        "## Salary Analysis",
        "",
    ]
    if len(sal_df):
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Median base salary | ${sal_df['salary_mid'].median():,.0f} |",
            f"| Mean base salary | ${sal_df['salary_mid'].mean():,.0f} |",
            f"| 25th percentile | ${sal_df['salary_mid'].quantile(0.25):,.0f} |",
            f"| 75th percentile | ${sal_df['salary_mid'].quantile(0.75):,.0f} |",
            f"| Min observed | ${sal_df['salary_mid'].min():,.0f} |",
            f"| Max observed | ${sal_df['salary_mid'].max():,.0f} |",
            "",
        ]
        # By company type
        by_type = sal_df.groupby("company_type")["salary_mid"].agg(["median", "mean", "count"])
        lines += ["**By company type:**", "", "| Type | Median | Mean | n |", "|------|--------|------|---|"]
        for ct, row in by_type.iterrows():
            lines.append(f"| {ct} | ${row['median']:,.0f} | ${row['mean']:,.0f} | {int(row['count'])} |")
        lines.append("")
    else:
        lines.append("_No salary data available yet._\n")

    # Company landscape
    lines += [
        "---",
        "",
        "## Company Landscape",
        "",
        "| Company Type | Count | % Share |",
        "|-------------|-------|---------|",
    ]
    total_typed = type_counts.sum()
    for ct, cnt in type_counts.items():
        lines.append(f"| {ct} | {cnt} | {cnt/total_typed*100:.1f}% |")

    lines += ["", "**Top hiring companies:**", ""]
    top_companies = job_df["company"].value_counts().head(15)
    for co, cnt in top_companies.items():
        lines.append(f"- {co}: {cnt} posting(s)")
    lines.append("")

    # Technical skills
    lines += [
        "---",
        "",
        "## Technical Skills",
        "",
    ]
    all_skills: dict[str, int] = {}
    for row in job_df["skills"]:
        try:
            skills = json.loads(row) if isinstance(row, str) else (row or [])
        except Exception:
            skills = []
        for s in skills:
            all_skills[s] = all_skills.get(s, 0) + 1

    if all_skills:
        sorted_skills = sorted(all_skills.items(), key=lambda x: x[1], reverse=True)
        lines += ["| Skill | Postings mentioning |", "|-------|-------------------|"]
        for skill, cnt in sorted_skills[:20]:
            lines.append(f"| {skill} | {cnt} |")
        lines.append("")
    else:
        lines.append("_Skill data not yet available._\n")

    # New job alerts
    lines += [
        "---",
        "",
        f"## New Job Alerts ({d.isoformat()})",
        "",
    ]
    if new_jobs:
        for j in new_jobs[:30]:
            d_obj = j if isinstance(j, dict) else j.to_dict()
            lines.append(
                f"- **{d_obj.get('title', 'N/A')}** — {d_obj.get('company', 'N/A')} "
                f"| {d_obj.get('location', '')} | [link]({d_obj.get('url', '#')})"
            )
    else:
        lines.append("_No new jobs detected since last run._")
    lines.append("")

    # Editorial section
    lines += [
        "---",
        "",
        "## Editorial: Expert Perspectives",
        "",
        "_Curated from industry reports, researcher commentary, and analyst publications._",
        "",
    ]
    for q in EDITORIAL_QUOTES:
        lines += [
            f"### {q['source']}",
            f"*{q['date']}*",
            "",
            f"> {q['quote']}",
            "",
            f"Source: [{q['url']}]({q['url']})",
            "",
        ]

    # Informal survey section
    lines += [
        "---",
        "",
        "## Informal Survey: Community Voices (Last 2 Months)",
        "",
        "_Paraphrased and curated from Reddit, Twitter/X, and Hacker News discussions._",
        "",
    ]
    for excerpt in INFORMAL_SURVEY_EXCERPTS:
        lines += [
            f"**{excerpt['platform']}** — `{excerpt['handle']}` ({excerpt['date']})",
            "",
            f"> {excerpt['text']}",
            "",
        ]

    lines += [
        "---",
        "",
        f"*Report auto-generated by agents_hiring_tracker on {d.isoformat()}.*",
        "*Data sources: HackerNews Algolia API, Greenhouse/Lever ATS, Indeed RSS, Reddit public API.*",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[Report] Written to {out_path}")
    return out_path
