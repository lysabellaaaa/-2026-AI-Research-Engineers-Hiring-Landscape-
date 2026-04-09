"""Statistical hypothesis testing for the 4 research hypotheses.

Each test returns a HypothesisResult with:
  - verdict: SUPPORTED | REJECTED | INSUFFICIENT_DATA
  - observed value, hypothesized value
  - p-value, confidence interval, sample n
  - plain-English summary
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class HypothesisResult:
    hypothesis_id: int
    hypothesis_text: str
    verdict: str                  # SUPPORTED | REJECTED | INSUFFICIENT_DATA
    observed: str                 # Human-readable observed value
    hypothesized: str             # Human-readable H0 value
    p_value: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    sample_n: int
    summary: str
    chart_data: dict = field(default_factory=dict)  # Data for mini-charts


MIN_SAMPLE = 10  # Minimum n before we report INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# H1: Agents has highest traction among AI subfields
# ---------------------------------------------------------------------------
def test_h1_agents_traction(df: pd.DataFrame) -> HypothesisResult:
    """
    H1: 'agents' subfield tag appears more frequently than any other subfield.
    Test: Is agents count significantly greater than the next-highest subfield?
    Uses proportion z-test: p_agents vs p_other (each vs rest).
    """
    import ast

    all_tags: list[str] = []
    for row in df["subfield_tags"]:
        if isinstance(row, str):
            try:
                tags = json.loads(row)
            except Exception:
                tags = [t.strip().strip("'\"") for t in row.strip("[]").split(",")]
        else:
            tags = row if row else []
        all_tags.extend([t for t in tags if t and t != "general_ai"])

    if len(all_tags) < MIN_SAMPLE:
        return HypothesisResult(
            hypothesis_id=1,
            hypothesis_text="Agents roles have the highest traction vs other AI subfields (CV, NLP, RL, etc.)",
            verdict="INSUFFICIENT_DATA",
            observed="N/A",
            hypothesized="agents > all other subfields",
            p_value=None, ci_low=None, ci_high=None,
            sample_n=len(all_tags),
            summary=f"Only {len(all_tags)} subfield tags found — need ≥{MIN_SAMPLE} to test.",
        )

    from collections import Counter
    counts = Counter(all_tags)
    total = sum(counts.values())
    top = counts.most_common(10)
    agents_count = counts.get("agents", 0)
    agents_pct = agents_count / total * 100

    # Is agents strictly the #1 subfield?
    rank = sorted(counts, key=counts.get, reverse=True)
    is_top = rank[0] == "agents" if rank else False

    # z-test: agents proportion vs next-highest
    verdict = "INSUFFICIENT_DATA"
    p_value = None
    ci_low = ci_high = None

    if agents_count > 0 and len(counts) > 1:
        second_tag = rank[1] if len(rank) > 1 and rank[0] == "agents" else rank[0]
        second_count = counts.get(second_tag, 0)
        # Two-proportion z-test: H0: p_agents == p_second
        n = total
        p1 = agents_count / n
        p2 = second_count / n
        p_pool = (agents_count + second_count) / (2 * n)
        se = np.sqrt(p_pool * (1 - p_pool) * (2 / n))
        if se > 0:
            z = (p1 - p2) / se
            p_value = stats.norm.sf(abs(z)) * 2  # two-tailed
            ci_low = (p1 - p2) - 1.96 * se
            ci_high = (p1 - p2) + 1.96 * se

        verdict = "SUPPORTED" if (is_top and (p_value is None or p_value < 0.05)) else "REJECTED"
        if not is_top:
            verdict = "REJECTED"

    summary_lines = [f"Top subfields by posting count (n={total} tags):"]
    for tag, cnt in top[:6]:
        pct = cnt / total * 100
        marker = " ← agents" if tag == "agents" else ""
        summary_lines.append(f"  {tag}: {cnt} ({pct:.1f}%){marker}")

    return HypothesisResult(
        hypothesis_id=1,
        hypothesis_text="Agents roles have the highest traction vs other AI subfields",
        verdict=verdict,
        observed=f"agents: {agents_count} tags ({agents_pct:.1f}%) — rank #{rank.index('agents')+1 if 'agents' in rank else 'N/A'}",
        hypothesized="agents is the #1 subfield tag",
        p_value=p_value, ci_low=ci_low, ci_high=ci_high,
        sample_n=total,
        summary="\n".join(summary_lines),
        chart_data={"labels": [t for t, _ in top[:8]], "values": [c for _, c in top[:8]]},
    )


# ---------------------------------------------------------------------------
# H2: Median base salary for junior roles = $150,000
# ---------------------------------------------------------------------------
def test_h2_junior_salary(df: pd.DataFrame) -> HypothesisResult:
    """
    H2: Median base salary for junior roles (experience_years_min <= 2) is $150K.
    Test: One-sample Wilcoxon signed-rank test vs median=150000.
    """
    H0_MEDIAN = 150_000

    # Junior = explicitly 0-2 years, or no experience min stated (assume junior-accessible)
    junior_mask = (
        df["experience_years_min"].isna() | (df["experience_years_min"] <= 2)
    )
    salary_df = df[junior_mask & df["salary_min"].notna() & df["salary_max"].notna()].copy()
    salary_df["salary_mid"] = (salary_df["salary_min"] + salary_df["salary_max"]) / 2

    n = len(salary_df)
    if n < MIN_SAMPLE:
        return HypothesisResult(
            hypothesis_id=2,
            hypothesis_text="Median base salary for junior Agents Research Engineer roles = $150,000",
            verdict="INSUFFICIENT_DATA",
            observed="N/A",
            hypothesized="$150,000",
            p_value=None, ci_low=None, ci_high=None,
            sample_n=n,
            summary=f"Only {n} junior postings with salary data (need ≥{MIN_SAMPLE}).",
        )

    salaries = salary_df["salary_mid"].values
    observed_median = float(np.median(salaries))

    # Wilcoxon signed-rank test (one-sample, compare to H0)
    shifted = salaries - H0_MEDIAN
    if len(shifted[shifted != 0]) < 5:
        p_value = None
        verdict = "INSUFFICIENT_DATA"
    else:
        stat, p_value = stats.wilcoxon(shifted, alternative="two-sided")
        verdict = "SUPPORTED" if p_value >= 0.05 else "REJECTED"

    # 95% CI for median via bootstrapping
    boot_medians = [
        np.median(np.random.choice(salaries, size=n, replace=True))
        for _ in range(2000)
    ]
    ci_low = float(np.percentile(boot_medians, 2.5))
    ci_high = float(np.percentile(boot_medians, 97.5))

    direction = "above" if observed_median > H0_MEDIAN else "below"
    return HypothesisResult(
        hypothesis_id=2,
        hypothesis_text="Median base salary for junior Agents Research Engineer roles = $150,000",
        verdict=verdict,
        observed=f"${observed_median:,.0f} (median of {n} junior postings)",
        hypothesized="$150,000",
        p_value=p_value, ci_low=ci_low, ci_high=ci_high,
        sample_n=n,
        summary=(
            f"Observed median: ${observed_median:,.0f} — {direction} hypothesis by "
            f"${abs(observed_median - H0_MEDIAN):,.0f}.\n"
            f"95% CI: [${ci_low:,.0f}, ${ci_high:,.0f}].\n"
            f"p-value: {p_value:.4f}" if p_value else "Insufficient variance for test."
        ),
        chart_data={"salaries": salaries.tolist(), "h0": H0_MEDIAN,
                    "median": observed_median, "ci": [ci_low, ci_high]},
    )


# ---------------------------------------------------------------------------
# H3: Only 30% of roles require >2 years experience
# ---------------------------------------------------------------------------
def test_h3_junior_accessibility(df: pd.DataFrame) -> HypothesisResult:
    """
    H3: 30% of roles require more than 2 years of experience
        (i.e., 70% are junior-accessible).
    Test: One-proportion z-test vs H0: p = 0.30.
    """
    H0_PROP = 0.30

    # Only non-reddit job postings with experience data
    exp_df = df[df["experience_years_min"].notna()].copy()
    n = len(exp_df)

    if n < MIN_SAMPLE:
        return HypothesisResult(
            hypothesis_id=3,
            hypothesis_text="30% of roles require >2 years of experience (70% are junior-accessible)",
            verdict="INSUFFICIENT_DATA",
            observed="N/A",
            hypothesized="30% require >2 years",
            p_value=None, ci_low=None, ci_high=None,
            sample_n=n,
            summary=f"Only {n} postings with experience data (need ≥{MIN_SAMPLE}).",
        )

    senior_mask = exp_df["experience_years_min"] > 2
    k = senior_mask.sum()
    p_hat = k / n

    # One-proportion z-test
    z = (p_hat - H0_PROP) / np.sqrt(H0_PROP * (1 - H0_PROP) / n)
    p_value = float(2 * stats.norm.sf(abs(z)))

    # Wilson CI
    ci_low = float((p_hat + z**2 / (2*n) - 1.96 * np.sqrt(p_hat*(1-p_hat)/n + z**2/(4*n**2))) /
                   (1 + z**2/n))
    ci_high = float((p_hat + z**2 / (2*n) + 1.96 * np.sqrt(p_hat*(1-p_hat)/n + z**2/(4*n**2))) /
                    (1 + z**2/n))

    verdict = "SUPPORTED" if p_value >= 0.05 else "REJECTED"

    exp_dist = exp_df["experience_years_min"].value_counts().sort_index()

    return HypothesisResult(
        hypothesis_id=3,
        hypothesis_text="30% of roles require >2 years of experience (70% are junior-accessible)",
        verdict=verdict,
        observed=f"{k}/{n} = {p_hat*100:.1f}% require >2 yrs experience",
        hypothesized="30.0% require >2 years",
        p_value=p_value, ci_low=ci_low * 100, ci_high=ci_high * 100,
        sample_n=n,
        summary=(
            f"Observed: {k} of {n} postings ({p_hat*100:.1f}%) require >2 years.\n"
            f"H₀: 30% require >2 years.\n"
            f"95% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%]. p={p_value:.4f}."
        ),
        chart_data={
            "exp_dist": {str(k): int(v) for k, v in exp_dist.items()},
            "senior_pct": float(p_hat * 100),
            "h0_pct": H0_PROP * 100,
        },
    )


# ---------------------------------------------------------------------------
# H4: Company distribution = 50% startup / 30% frontier / 20% other
# ---------------------------------------------------------------------------
def test_h4_company_distribution(df: pd.DataFrame) -> HypothesisResult:
    """
    H4: 50% startups, 30% frontier labs, 20% big tech + AI safety.
    Test: Chi-square goodness-of-fit vs expected proportions.
    """
    H0 = {
        "startup": 0.50,
        "frontier_lab": 0.30,
        "big_tech": 0.10,
        "ai_safety": 0.10,
    }

    type_counts = df[df["source"] != "reddit"]["company_type"].value_counts()
    # Merge unknowns into startup (conservative)
    if "unknown" in type_counts:
        type_counts["startup"] = type_counts.get("startup", 0) + type_counts["unknown"]
        type_counts = type_counts.drop("unknown", errors="ignore")

    n = int(type_counts.sum())
    if n < MIN_SAMPLE:
        return HypothesisResult(
            hypothesis_id=4,
            hypothesis_text="50% startups / 30% frontier labs / 10% big tech / 10% AI safety",
            verdict="INSUFFICIENT_DATA",
            observed="N/A",
            hypothesized="50/30/10/10",
            p_value=None, ci_low=None, ci_high=None,
            sample_n=n,
            summary=f"Only {n} classified postings (need ≥{MIN_SAMPLE}).",
        )

    categories = list(H0.keys())
    observed_counts = np.array([type_counts.get(cat, 0) for cat in categories], dtype=float)
    expected_counts = np.array([H0[cat] * n for cat in categories])

    # Chi-square goodness-of-fit
    chi2, p_value = stats.chisquare(f_obs=observed_counts, f_exp=expected_counts)
    verdict = "SUPPORTED" if p_value >= 0.05 else "REJECTED"

    obs_pcts = {cat: float(type_counts.get(cat, 0) / n * 100) for cat in categories}
    summary_rows = [f"Company type distribution (n={n}):"]
    for cat in categories:
        obs = obs_pcts[cat]
        exp = H0[cat] * 100
        summary_rows.append(f"  {cat}: {obs:.1f}% observed vs {exp:.0f}% expected")
    summary_rows.append(f"χ²={chi2:.2f}, p={p_value:.4f}")

    return HypothesisResult(
        hypothesis_id=4,
        hypothesis_text="50% startups / 30% frontier labs / 10% big tech / 10% AI safety",
        verdict=verdict,
        observed=" / ".join(f"{cat}: {obs_pcts[cat]:.1f}%" for cat in categories),
        hypothesized="50% / 30% / 10% / 10%",
        p_value=float(p_value), ci_low=None, ci_high=None,
        sample_n=n,
        summary="\n".join(summary_rows),
        chart_data={
            "categories": categories,
            "observed": [obs_pcts[c] for c in categories],
            "expected": [H0[c] * 100 for c in categories],
        },
    )


# ---------------------------------------------------------------------------
# Run all 4 tests
# ---------------------------------------------------------------------------
def run_all_hypotheses(df: pd.DataFrame) -> list[HypothesisResult]:
    return [
        test_h1_agents_traction(df),
        test_h2_junior_salary(df),
        test_h3_junior_accessibility(df),
        test_h4_company_distribution(df),
    ]
