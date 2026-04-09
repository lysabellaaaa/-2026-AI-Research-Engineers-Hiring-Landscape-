# Agents Research Engineer — Bay Area Hiring Tracker

> A living intelligence system that continuously monitors, analyzes, and visualizes the Bay Area job market for **Agents Research Engineer** roles — updated daily, hypothesis-tested statistically, and surfaced through an interactive Streamlit dashboard.

---

## What this is

This project answers a single question with rigor:

**What does the Bay Area market for Agents Research Engineers actually look like right now — salary, seniority, companies, skills — and how does it compare to what people assume?**

It does this by:

- Scraping job postings every day from HackerNews, Greenhouse/Lever/Ashby ATS, and Reddit
- Extracting structured fields (salary, experience, skills, company type) from raw text using NLP
- Running 4 pre-registered statistical hypothesis tests against live data
- Generating a dated Markdown analysis report
- Alerting on new job postings detected since the prior run
- Displaying everything in a 5-tab Streamlit dashboard that auto-refreshes every 5 minutes

---

## Preliminary Findings

> **Data snapshot — April 9, 2026 · 708 job postings · 6-month window**

### Hypothesis Test Results

| # | Hypothesis | Verdict | Key Number |
|---|-----------|---------|-----------|
| H1 | Agents is the highest-traction AI subfield vs CV, NLP, RL | ✅ **SUPPORTED** | Agents = **50.6%** of all subfield tags — more than NLP + CV + RL + MLOps combined |
| H2 | Median junior base salary = $150,000 | ❌ **REJECTED** | Observed median = **$175,000** (95% CI: $160K–$196K) |
| H3 | 30% of roles require >2 years experience | ❌ **REJECTED** | Actual rate = **70.4%** — the hypothesis is essentially inverted |
| H4 | 50% startups / 30% frontier labs / 10% big tech / 10% AI safety | ❌ **REJECTED** | HN skews to 94.5% startup; ATS skews to 97% frontier lab — true distribution lies between |

### Key Market Facts

```
Median base salary (junior roles, ≤2 yrs)   $175,000
Salary range observed                        $35K – $350K base
Roles explicitly requiring >2 yrs            70.4%
Top required skill                           Python (234 postings)
Highest-rising skill                         MCP / Model Context Protocol
Subfield share: agents                       50.6%  ← #1
Subfield share: LLM                          28.1%  ← #2
Subfield share: CV                           9.3%   ← #3
```

### Subfield Rankings

```
agents  ████████████████████████████████████████████████████  50.6%
LLM     ████████████████████████████                          28.1%
CV      █████████                                              9.3%
RL      █████                                                  4.7%
MLOps   █████                                                  4.3%
NLP     ███                                                    3.0%
```

### Salary Distribution by Company Type

```
Frontier lab (Anthropic, Mistral, METR)  ████████████████████  $290K–$340K base
Big tech                                 ████████████████      $218K base
Startup                                  ██████████████        $175K median
─────────────────────────────────────────────────────────────
                                         H₂ hypothesis: $150K ↑
```

> Full analysis with statistical detail: [`FINDINGS.md`](FINDINGS.md)
> Daily auto-generated reports: [`reports/`](reports/)

---

## Dashboard

The Streamlit dashboard has 5 tabs:

### Tab 1 — Overview
KPI cards, source breakdown pie chart, daily scrape volume bar chart, and a live postings table.

![Overview tab showing KPI cards for total postings, median salary, experience filter, and top company, with a pie chart of data sources and bar chart of daily volume](docs/screenshots/tab1_overview.png)

---

### Tab 2 — Hypothesis Testing
Four hypothesis cards, each showing verdict badge, observed vs. hypothesized value, p-value, confidence interval, and a mini-chart.

![Hypothesis testing tab with four cards: H1 SUPPORTED in green, H2 REJECTED in red, H3 REJECTED in red, H4 REJECTED in red, each with statistical detail and visualization](docs/screenshots/tab2_hypotheses.png)

**Example card layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  H1: Agents roles have the highest traction vs other AI     │
│      subfields                                              │
│                                                             │
│  ✅ SUPPORTED                                               │
│                                                             │
│  Observed:      agents: 342 tags (50.6%) — rank #1          │
│  Hypothesized:  agents is the #1 subfield tag               │
│  p-value:       < 0.0001   |   n: 676                       │
│                                                             │
│  [▶ Full statistical detail]           [Bar chart →]        │
└─────────────────────────────────────────────────────────────┘
```

---

### Tab 3 — Salary & Experience
Salary histogram with H₂ and observed-median markers, box plots by company type, scatter of salary vs. experience, and experience distribution bar chart.

![Salary and experience tab showing a histogram of base salary distribution with marker lines at $150K hypothesis and $175K observed median, plus scatter plot of salary vs years experience](docs/screenshots/tab3_salary.png)

---

### Tab 4 — Companies & Skills
Company type pie chart (with H₄ expected proportions noted), top 15 hiring companies bar chart, top 25 required skills horizontal bar, skill word cloud, and subfield comparison bar chart.

![Companies and skills tab showing pie chart of company types, horizontal bar chart of top 15 companies led by Anthropic, and skills frequency bar chart led by Python and TypeScript](docs/screenshots/tab4_companies.png)

---

### Tab 5 — Trends, Alerts & Community
Daily posting volume line chart, new job alerts feed table, collapsible editorial quotes from 6 expert sources, and collapsible community voice excerpts from Reddit/HN/Twitter.

![Trends tab showing daily line chart of posting volume over 30 days, scrollable new jobs alert table, and expandable editorial sections from LangChain, McKinsey, Stanford AI Index](docs/screenshots/tab5_trends.png)

> **To add screenshots:** run the dashboard, take a screenshot of each tab, and save to `docs/screenshots/tab{N}_{name}.png`.

---

## Quickstart

### Prerequisites

- Python 3.11+
- Windows 10/11 (tested), macOS/Linux compatible

### 1. Install dependencies

```powershell
cd "agents_hiring_tracker"
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Run the pipeline once (seeds the database)

```powershell
python run_once.py
```

This will:
- Scrape HackerNews (6-month hiring threads), Greenhouse/Lever/Ashby ATS, and Reddit
- Extract salary, experience, and skills from each posting
- Classify companies by type (frontier lab / AI safety / startup / big tech)
- Run all 4 hypothesis tests
- Save a Parquet snapshot and checkpoint
- Alert on new jobs vs. prior run
- Write a dated Markdown report to `reports/`

To run a single source only:

```powershell
python run_once.py --source hn           # HackerNews only
python run_once.py --source greenhouse   # ATS pages only
python run_once.py --source reddit       # Community sentiment only
python run_once.py --no-report           # Skip report generation
```

### 3. Launch the dashboard

```powershell
streamlit run dashboard/app.py
```

Then open **http://localhost:8501** in your browser.

> The dashboard auto-refreshes every **5 minutes**. Leave it running and it will pick up new data automatically as the scheduler writes to the database.

### 4. Start the daily scheduler (optional)

```powershell
python scheduler.py
```

This runs the full pipeline every day at **07:00 Pacific Time**. To trigger immediately and then start the schedule:

```powershell
python scheduler.py --run-now
```

To change the run time:

```powershell
python scheduler.py --hour 9 --minute 30   # Run at 09:30 PT daily
```

---

## Project Structure

```
agents_hiring_tracker/
│
├── scrapers/
│   ├── base.py                  JobPosting dataclass + BaseScraper ABC
│   ├── hn_scraper.py            HackerNews Algolia API (6-month lookback)
│   ├── greenhouse_scraper.py    Greenhouse + Lever + Ashby ATS pages
│   ├── indeed_scraper.py        Indeed RSS + page scraping
│   └── reddit_scraper.py        Reddit public JSON API (2-month sentiment)
│
├── analysis/
│   ├── extractor.py             Regex NLP: salary, experience, skills, subfields
│   ├── classifier.py            Company type classifier (frontier/safety/big tech/startup)
│   ├── hypotheses.py            4 statistical tests (Wilcoxon, z-test, chi-square)
│   ├── report_generator.py      Daily Markdown report writer
│   └── db.py                    DuckDB schema, ingestion, query helpers
│
├── dashboard/
│   └── app.py                   Streamlit 5-tab dashboard
│
├── alerts/
│   └── job_alerts.py            Checkpoint diff → new job detection + log
│
├── data/
│   ├── jobs.db                  DuckDB database (main analytics store)
│   ├── raw/                     Raw JSON per source per date
│   ├── processed/               Cleaned Parquet snapshots (one per day)
│   └── checkpoints/             Job ID sets for new-job diff detection
│
├── reports/                     Auto-generated daily Markdown analysis reports
├── docs/screenshots/            Dashboard screenshots (add manually)
│
├── FINDINGS.md                  Full research findings document
├── run_once.py                  Manual pipeline trigger
├── scheduler.py                 APScheduler daily runner (07:00 PT)
└── requirements.txt
```

---

## Data Sources

| Source | What it provides | Auth required |
|--------|-----------------|---------------|
| HackerNews Algolia API | "Who is Hiring?" monthly threads (6 months) | None |
| Greenhouse Board API | Anthropic, Symbolica AI job listings | None (public) |
| Lever Postings API | Mistral AI, METR job listings | None (public) |
| Ashby Job Board API | Cohere, Sierra, Letta job listings | None (public) |
| Reddit public JSON | Community discussion and sentiment | None |
| Indeed | RSS + page scraping | None (currently blocked) |

---

## How New Job Alerts Work

Every pipeline run compares today's scraped job IDs against the previous day's checkpoint:

```
Today's IDs  ─────────┐
                       ▼
              set difference  →  new_jobs_YYYY-MM-DD.json
                       ▲
Yesterday's IDs ───────┘
```

New jobs appear in:
- `alerts/new_jobs_YYYY-MM-DD.json` — raw JSON log
- Dashboard Tab 5 — scrollable alert feed table

---

## Statistical Methods

| Hypothesis | Test | Null hypothesis |
|-----------|------|----------------|
| H1 (agents traction) | Two-proportion z-test | p_agents = p_second_subfield |
| H2 (junior salary) | Wilcoxon signed-rank (one-sample) + bootstrap CI | median = $150,000 |
| H3 (experience accessibility) | One-proportion z-test + Wilson CI | p(>2 yrs) = 0.30 |
| H4 (company distribution) | Chi-square goodness-of-fit | observed ~ [0.50, 0.30, 0.10, 0.10] |

Significance threshold: **α = 0.05**. Minimum sample for testing: **n = 10**.

---

## Further Reading

- [`FINDINGS.md`](FINDINGS.md) — Full 12-section research findings document with editorial and community survey sections
- [`reports/analysis_2026-04-09.md`](reports/analysis_2026-04-09.md) — Latest auto-generated daily report
- [LangChain State of Agent Engineering 2025](https://www.langchain.com/state-of-agent-engineering)
- [Stanford AI Index 2025 — Economy Chapter](https://hai.stanford.edu/assets/files/hai_ai-index-report-2025_chapter4_final.pdf)
- [McKinsey State of AI 2025](https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai)
- [Nathan Lambert — Thoughts on the AI hiring market](https://www.interconnects.ai/p/thoughts-on-the-hiring-market-in)
