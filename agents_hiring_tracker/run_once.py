"""Manual full-pipeline trigger.

Usage:
    python run_once.py               # run all sources
    python run_once.py --source hn   # run only HackerNews
    python run_once.py --source greenhouse
    python run_once.py --source indeed
    python run_once.py --source reddit
    python run_once.py --no-report   # skip report generation
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"


def run_scrapers(source_filter: str | None = None) -> list:
    from scrapers.hn_scraper import HNScraper
    from scrapers.greenhouse_scraper import GreenhouseScraper
    from scrapers.indeed_scraper import IndeedScraper
    from scrapers.reddit_scraper import RedditScraper
    from analysis.extractor import enrich_posting
    from analysis.classifier import enrich_company_type

    all_postings = []

    scrapers = {
        "hn": HNScraper(DATA_DIR),
        "greenhouse": GreenhouseScraper(DATA_DIR),
        "indeed": IndeedScraper(DATA_DIR),
        "reddit": RedditScraper(DATA_DIR),
    }

    for name, scraper in scrapers.items():
        if source_filter and name != source_filter:
            continue
        print(f"\n{'='*50}")
        print(f"Running {name.upper()} scraper...")
        print("=" * 50)
        try:
            postings = scraper.run()
            for p in postings:
                enrich_posting(p)
                enrich_company_type(p)
            all_postings.extend(postings)
            print(f"[{name}] Saved {len(postings)} postings")
        except Exception as e:
            print(f"[{name}] FAILED: {e}")
            import traceback
            traceback.print_exc()

    return all_postings


def run_pipeline(source_filter: str | None = None, generate_report: bool = True):
    from analysis.db import get_conn, upsert_postings, load_all_jobs
    from analysis.hypotheses import run_all_hypotheses
    from analysis.report_generator import generate_report as gen_report
    from alerts.job_alerts import (
        get_previous_checkpoint, detect_new_jobs,
        save_checkpoint, save_alert_log
    )

    print(f"\nAgents Hiring Tracker — Pipeline run {date.today().isoformat()}")
    print("=" * 60)

    # 1. Scrape
    postings = run_scrapers(source_filter)
    print(f"\nTotal postings fetched: {len(postings)}")

    if not postings:
        print("No postings fetched — check scraper output above.")
        return

    # 2. Diff against previous checkpoint for alert detection
    previous_ids = get_previous_checkpoint()
    new_jobs = detect_new_jobs(postings, previous_ids)
    print(f"New jobs (not seen before): {len(new_jobs)}")

    # 3. Save to DuckDB
    conn = get_conn()
    inserted = upsert_postings(postings, conn)
    print(f"Upserted {inserted} rows to DuckDB")

    # 4. Save checkpoint
    today_ids = {p.id for p in postings}
    save_checkpoint(today_ids)
    print(f"Checkpoint saved ({len(today_ids)} IDs)")

    # 5. Save alert log
    if new_jobs:
        alert_path = save_alert_log(new_jobs)
        print(f"Alert log: {alert_path}")

    # 6. Save processed Parquet snapshot
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    processed_dir = ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    rows = [p.to_dict() for p in postings]
    pq_path = processed_dir / f"{date.today().isoformat()}.parquet"
    df = pd.DataFrame(rows)
    # Serialize list columns
    for col in ["skills", "subfield_tags"]:
        if col in df.columns:
            df[col] = df[col].apply(json.dumps)
    df.to_parquet(pq_path, index=False)
    print(f"Parquet snapshot: {pq_path}")

    # 7. Run hypothesis tests + generate report
    if generate_report:
        all_df = load_all_jobs(conn)
        conn.close()
        if not all_df.empty:
            h_results = run_all_hypotheses(all_df)
            report_path = gen_report(all_df, h_results, new_jobs)
            print(f"\nReport: {report_path}")

            # Print hypothesis summary
            print("\n--- Hypothesis Results ---")
            for r in h_results:
                print(f"H{r.hypothesis_id}: {r.verdict} | {r.observed}")
        else:
            conn.close()
    else:
        conn.close()

    print(f"\nPipeline complete. Run 'streamlit run dashboard/app.py' to view the dashboard.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the agents hiring tracker pipeline")
    parser.add_argument("--source", type=str, default=None,
                        help="Run only this source: hn | greenhouse | indeed | reddit")
    parser.add_argument("--no-report", action="store_true",
                        help="Skip report generation")
    args = parser.parse_args()

    run_pipeline(
        source_filter=args.source,
        generate_report=not args.no_report,
    )
