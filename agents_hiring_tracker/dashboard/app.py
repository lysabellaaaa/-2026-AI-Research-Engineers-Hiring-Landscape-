"""Streamlit dashboard — 5 tabs:
  1. Overview (KPIs)
  2. Hypothesis Testing
  3. Salary & Experience
  4. Companies & Skills
  5. Trends, Alerts & Community
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from analysis.db import get_conn, load_all_jobs, load_jobs_with_salary, load_reddit_posts, daily_trend
from analysis.hypotheses import run_all_hypotheses
from analysis.report_generator import EDITORIAL_QUOTES, INFORMAL_SURVEY_EXCERPTS
from alerts.job_alerts import load_latest_alerts

# ── page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agents Research Engineer — Bay Area Hiring Tracker",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.verdict-supported  { color:#22c55e; font-weight:700; font-size:1.1em; }
.verdict-rejected   { color:#ef4444; font-weight:700; font-size:1.1em; }
.verdict-insufficient{ color:#f59e0b; font-weight:700; font-size:1.1em; }
.kpi-box { background:#1e293b; border-radius:10px; padding:16px 20px; text-align:center; }
.kpi-val { font-size:2em; font-weight:700; color:#38bdf8; }
.kpi-lbl { font-size:0.85em; color:#94a3b8; }
</style>
""", unsafe_allow_html=True)

# ── data loading (cached per run) ────────────────────────────────────────────
@st.cache_data(ttl=300)
def _load_data():
    try:
        conn = get_conn()
        df = load_all_jobs(conn)
        sal_df = load_jobs_with_salary(conn)
        reddit_df = load_reddit_posts(conn)
        trend_df = daily_trend(conn)
        conn.close()
        return df, sal_df, reddit_df, trend_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=300)
def _run_hypotheses(df_json: str):
    df = pd.read_json(df_json)
    if df.empty:
        return []
    return run_all_hypotheses(df)


def _parse_list_col(series: pd.Series) -> pd.Series:
    """Parse JSON-string list columns into Python lists."""
    def parse(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [x.strip().strip("'\"") for x in v.strip("[]").split(",") if x.strip()]
        return []
    return series.apply(parse)


# ════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════
st.title("Agents Research Engineer — Bay Area Hiring Tracker")
st.caption(
    "Live data from HackerNews, Greenhouse/Lever ATS, Indeed, and Reddit. "
    "Updated daily at 07:00. Refresh every 5 min."
)

# ── load ─────────────────────────────────────────────────────────────────────
df, sal_df, reddit_df, trend_df = _load_data()
new_jobs_raw = load_latest_alerts()

# Hypothesis results
h_results = _run_hypotheses(df.to_json()) if not df.empty else []

# Parse list columns
if not df.empty:
    df["skills_list"] = _parse_list_col(df["skills"])
    df["tags_list"] = _parse_list_col(df["subfield_tags"])

n_total = len(df)
n_new = len(new_jobs_raw)
median_sal = sal_df["salary_mid"].median() if not sal_df.empty else None

# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Hypothesis Testing", "Salary & Experience",
    "Companies & Skills", "Trends, Alerts & Community"
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Market Snapshot")

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Postings", n_total, delta=f"+{n_new} today")
    with col2:
        st.metric("Median Base Salary",
                  f"${median_sal:,.0f}" if median_sal else "N/A")
    with col3:
        if not df.empty and "experience_years_min" in df.columns:
            exp_df = df[df["experience_years_min"].notna()]
            pct_senior = (exp_df["experience_years_min"] > 2).mean() * 100 if len(exp_df) else 0
            st.metric("Roles Requiring >2 Yrs", f"{pct_senior:.1f}%")
        else:
            st.metric("Roles Requiring >2 Yrs", "N/A")
    with col4:
        if not df.empty:
            top_co = df["company"].value_counts().idxmax() if len(df) else "N/A"
            st.metric("Top Hiring Company", top_co)
        else:
            st.metric("Top Hiring Company", "N/A")

    st.divider()

    if df.empty:
        st.info(
            "No data yet. Run `python run_once.py` to populate the database, "
            "then refresh this page."
        )
    else:
        # Source breakdown
        col_a, col_b = st.columns(2)
        with col_a:
            src_counts = df["source"].value_counts().reset_index()
            src_counts.columns = ["Source", "Count"]
            fig = px.pie(src_counts, names="Source", values="Count",
                         title="Postings by Data Source",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            if not trend_df.empty:
                fig2 = px.bar(trend_df, x="scraped_date", y="new_jobs",
                              title="Daily Scrape Volume",
                              labels={"scraped_date": "Date", "new_jobs": "Postings"},
                              color_discrete_sequence=["#38bdf8"])
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No trend data yet.")

        # Recent postings table
        st.subheader("Recent Postings")
        show_cols = ["title", "company", "company_type", "location",
                     "salary_min", "salary_max", "experience_years_min", "source", "scraped_date"]
        show_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(
            df[show_cols].sort_values("scraped_date", ascending=False).head(30),
            use_container_width=True, height=400,
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — HYPOTHESIS TESTING
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Hypothesis Test Results")
    st.caption(
        "Testing 4 a-priori hypotheses about the Bay Area Agents Research Engineer market. "
        "Statistical tests run on live scraped data."
    )

    VERDICT_COLOR = {
        "SUPPORTED": "#22c55e",
        "REJECTED": "#ef4444",
        "INSUFFICIENT_DATA": "#f59e0b",
    }
    VERDICT_ICON = {
        "SUPPORTED": "✅",
        "REJECTED": "❌",
        "INSUFFICIENT_DATA": "⚠️",
    }

    if not h_results:
        st.info("Run `python run_once.py` first to generate hypothesis data.")
    else:
        for r in h_results:
            with st.container(border=True):
                icon = VERDICT_ICON.get(r.verdict, "")
                color = VERDICT_COLOR.get(r.verdict, "#94a3b8")
                col_text, col_chart = st.columns([2, 1])

                with col_text:
                    st.markdown(
                        f"### H{r.hypothesis_id}: {r.hypothesis_text}\n\n"
                        f"<span style='color:{color};font-weight:700;font-size:1.1em'>"
                        f"{icon} {r.verdict}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Observed:** {r.observed}")
                    st.markdown(f"**Hypothesized:** {r.hypothesized}")
                    if r.p_value is not None:
                        st.markdown(
                            f"**p-value:** `{r.p_value:.4f}` &nbsp;|&nbsp; "
                            f"**n:** `{r.sample_n}`",
                            unsafe_allow_html=True,
                        )
                    if r.ci_low is not None and r.ci_high is not None:
                        st.markdown(f"**95% CI:** [{r.ci_low:.1f}, {r.ci_high:.1f}]")
                    with st.expander("Full statistical detail"):
                        st.code(r.summary)

                with col_chart:
                    cd = r.chart_data
                    if r.hypothesis_id == 1 and cd.get("labels"):
                        fig = px.bar(
                            x=cd["labels"], y=cd["values"],
                            labels={"x": "Subfield", "y": "Tag count"},
                            color=cd["labels"],
                            color_discrete_sequence=px.colors.qualitative.Vivid,
                        )
                        fig.update_layout(showlegend=False, margin=dict(t=10, b=10))
                        st.plotly_chart(fig, use_container_width=True)

                    elif r.hypothesis_id == 2 and cd.get("salaries"):
                        fig = go.Figure()
                        fig.add_trace(go.Histogram(
                            x=cd["salaries"], name="Salaries",
                            marker_color="#38bdf8", opacity=0.75,
                        ))
                        fig.add_vline(x=cd["median"], line_color="#22c55e",
                                      line_dash="solid", annotation_text="Observed median")
                        fig.add_vline(x=cd["h0"], line_color="#ef4444",
                                      line_dash="dash", annotation_text="H₀ $150K")
                        fig.update_layout(showlegend=False, margin=dict(t=10, b=10),
                                          xaxis_title="Salary ($)")
                        st.plotly_chart(fig, use_container_width=True)

                    elif r.hypothesis_id == 3 and cd.get("exp_dist"):
                        exp_data = cd["exp_dist"]
                        fig = go.Figure(go.Bar(
                            x=list(exp_data.keys()),
                            y=list(exp_data.values()),
                            marker_color="#38bdf8",
                        ))
                        fig.add_hline(y=r.sample_n * 0.30, line_dash="dash",
                                      line_color="#ef4444",
                                      annotation_text="H₀ threshold (30%)")
                        fig.update_layout(
                            xaxis_title="Min years experience", yaxis_title="Count",
                            margin=dict(t=10, b=10),
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    elif r.hypothesis_id == 4 and cd.get("categories"):
                        fig = go.Figure(data=[
                            go.Bar(name="Observed", x=cd["categories"],
                                   y=cd["observed"], marker_color="#38bdf8"),
                            go.Bar(name="Expected (H₀)", x=cd["categories"],
                                   y=cd["expected"], marker_color="#f59e0b"),
                        ])
                        fig.update_layout(barmode="group", margin=dict(t=10, b=10),
                                          yaxis_title="%")
                        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — SALARY & EXPERIENCE
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Salary & Experience Analysis")

    if sal_df.empty:
        st.info("No salary data yet. Run the scrapers to populate.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.histogram(
                sal_df, x="salary_mid", nbins=30,
                title="Base Salary Distribution",
                labels={"salary_mid": "Midpoint Base Salary ($)"},
                color_discrete_sequence=["#38bdf8"],
            )
            fig.add_vline(x=150_000, line_dash="dash", line_color="#f59e0b",
                          annotation_text="H₂ hypothesis $150K")
            fig.add_vline(x=sal_df["salary_mid"].median(), line_dash="solid",
                          line_color="#22c55e",
                          annotation_text=f"Observed median ${sal_df['salary_mid'].median():,.0f}")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.box(
                sal_df, x="company_type", y="salary_mid",
                title="Salary by Company Type",
                labels={"salary_mid": "Base Salary ($)", "company_type": "Company Type"},
                color="company_type",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Scatter: salary vs experience
        exp_sal = sal_df[sal_df["experience_years_min"].notna()].copy()
        if not exp_sal.empty:
            fig3 = px.scatter(
                exp_sal, x="experience_years_min", y="salary_mid",
                color="company_type", hover_data=["title", "company"],
                title="Salary vs. Experience Required",
                labels={
                    "experience_years_min": "Min Years Experience",
                    "salary_mid": "Base Salary ($)",
                },
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig3.add_hline(y=150_000, line_dash="dash", line_color="#f59e0b",
                           annotation_text="$150K marker")
            st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.subheader("Experience Requirements")

    if not df.empty and "experience_years_min" in df.columns:
        exp_df = df[df["experience_years_min"].notna() & (df["source"] != "reddit")]
        if not exp_df.empty:
            exp_counts = exp_df["experience_years_min"].value_counts().sort_index().reset_index()
            exp_counts.columns = ["Min Years", "Count"]
            fig4 = px.bar(
                exp_counts, x="Min Years", y="Count",
                title="Distribution of Minimum Experience Requirements",
                color_discrete_sequence=["#818cf8"],
            )
            pct_senior = (exp_df["experience_years_min"] > 2).mean() * 100
            fig4.add_vline(x=2, line_dash="dash", line_color="#ef4444",
                           annotation_text=f"{pct_senior:.1f}% require >2 yrs")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No experience data extracted yet.")
    else:
        st.info("No experience data available.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — COMPANIES & SKILLS
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Company Landscape")

    if df.empty:
        st.info("No data yet.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            type_counts = df[df["source"] != "reddit"]["company_type"].value_counts().reset_index()
            type_counts.columns = ["Type", "Count"]
            fig = px.pie(
                type_counts, names="Type", values="Count",
                title="Company Type Breakdown",
                color_discrete_map={
                    "frontier_lab": "#38bdf8",
                    "ai_safety": "#a78bfa",
                    "big_tech": "#34d399",
                    "startup": "#fb923c",
                    "unknown": "#94a3b8",
                },
            )
            # Add expected rings annotation
            st.plotly_chart(fig, use_container_width=True)
            st.caption("H₄ expects: 50% startup / 30% frontier lab / 10% big tech / 10% AI safety")

        with col2:
            top_cos = df[df["source"] != "reddit"]["company"].value_counts().head(15).reset_index()
            top_cos.columns = ["Company", "Postings"]
            fig2 = px.bar(
                top_cos, x="Postings", y="Company", orientation="h",
                title="Top 15 Hiring Companies",
                color="Postings",
                color_continuous_scale="Blues",
            )
            fig2.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("Technical Skills")

    all_skills: dict[str, int] = {}
    if not df.empty and "skills_list" in df.columns:
        for skills in df["skills_list"]:
            for s in (skills or []):
                all_skills[s] = all_skills.get(s, 0) + 1

    if all_skills:
        skill_df = pd.DataFrame(
            sorted(all_skills.items(), key=lambda x: x[1], reverse=True),
            columns=["Skill", "Count"],
        ).head(25)

        fig3 = px.bar(
            skill_df, x="Count", y="Skill", orientation="h",
            title="Top 25 Required Skills (by posting frequency)",
            color="Count", color_continuous_scale="Teal",
        )
        fig3.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig3, use_container_width=True)

        # Word cloud attempt
        try:
            from wordcloud import WordCloud
            import matplotlib.pyplot as plt
            wc = WordCloud(
                width=800, height=300, background_color="#0f172a",
                colormap="Blues", max_words=60,
            ).generate_from_frequencies(all_skills)
            fig_wc, ax = plt.subplots(figsize=(10, 3))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            fig_wc.patch.set_facecolor("#0f172a")
            st.pyplot(fig_wc)
        except Exception:
            pass
    else:
        st.info("Skills will appear after data is scraped and processed.")

    st.divider()
    st.subheader("Subfield Comparison (Agents vs Others)")

    all_tags: dict[str, int] = {}
    if not df.empty and "tags_list" in df.columns:
        for tags in df[df["source"] != "reddit"]["tags_list"]:
            for t in (tags or []):
                if t and t != "general_ai":
                    all_tags[t] = all_tags.get(t, 0) + 1

    if all_tags:
        tag_df = pd.DataFrame(
            sorted(all_tags.items(), key=lambda x: x[1], reverse=True),
            columns=["Subfield", "Count"],
        )
        colors = ["#38bdf8" if s == "agents" else "#64748b" for s in tag_df["Subfield"]]
        fig4 = px.bar(
            tag_df, x="Subfield", y="Count",
            title="Subfield Tags in Job Postings (blue = agents)",
            color="Subfield",
            color_discrete_sequence=colors,
        )
        fig4.update_layout(showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)
        st.caption("H₁ expects 'agents' to be the top-ranked subfield.")
    else:
        st.info("Subfield data will appear after scraping.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — TRENDS, ALERTS & COMMUNITY
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.subheader("Posting Trends")

    if not trend_df.empty:
        fig = px.line(
            trend_df, x="scraped_date", y="new_jobs",
            title="Daily Job Posting Volume (last 30 days)",
            labels={"scraped_date": "Date", "new_jobs": "Postings scraped"},
            markers=True, line_shape="spline",
            color_discrete_sequence=["#38bdf8"],
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Trend data builds up after multiple daily runs.")

    st.divider()

    # New job alerts feed
    st.subheader(f"New Job Alerts (since last run) — {n_new} new")
    if new_jobs_raw:
        alert_df = pd.DataFrame(new_jobs_raw)[
            ["title", "company", "company_type", "location", "salary_min", "salary_max", "url", "scraped_date"]
        ]
        st.dataframe(alert_df, use_container_width=True, height=300)
    else:
        st.info("No new jobs detected since last run. Alerts populate after the second daily run.")

    st.divider()

    # Editorial section
    st.subheader("Editorial: Expert Perspectives")
    st.caption("Curated from industry reports and researcher commentary.")

    for q in EDITORIAL_QUOTES:
        with st.expander(f"{q['source']} ({q['date']})"):
            st.markdown(f"> {q['quote']}")
            st.markdown(f"[Read source]({q['url']})")

    st.divider()

    # Informal survey
    st.subheader("Informal Survey: Community Voices (Last 2 Months)")
    st.caption("Paraphrased and curated from Reddit, Twitter/X, and Hacker News.")

    for excerpt in INFORMAL_SURVEY_EXCERPTS:
        with st.expander(f"{excerpt['platform']} — {excerpt['handle']} ({excerpt['date']})"):
            st.markdown(f"> {excerpt['text']}")

    # Reddit data feed
    if not reddit_df.empty:
        st.divider()
        st.subheader("Live Reddit Discussions")
        st.dataframe(
            reddit_df[["title", "url", "scraped_date"]].sort_values("scraped_date", ascending=False).head(20),
            use_container_width=True,
        )

# ── auto-refresh footer ──────────────────────────────────────────────────────
st.divider()
st.caption(
    "Auto-refreshes every 5 minutes. "
    "Run `python scheduler.py` to start the daily pipeline. "
    "Manual trigger: `python run_once.py`"
)

# Trigger rerun after 5 minutes for live updates
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > 300:
    st.session_state.last_refresh = time.time()
    st.rerun()
