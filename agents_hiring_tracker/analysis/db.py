"""DuckDB schema, ingestion, and query helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id                   VARCHAR PRIMARY KEY,
    title                VARCHAR,
    company              VARCHAR,
    company_type         VARCHAR,
    location             VARCHAR,
    salary_min           DOUBLE,
    salary_max           DOUBLE,
    salary_tc_min        DOUBLE,
    salary_tc_max        DOUBLE,
    experience_years_min INTEGER,
    experience_years_max INTEGER,
    skills               VARCHAR,        -- JSON array stored as string
    subfield_tags        VARCHAR,        -- JSON array stored as string
    source               VARCHAR,
    url                  VARCHAR,
    raw_text             VARCHAR,
    scraped_date         DATE,
    posted_date          DATE,
    is_new               BOOLEAN DEFAULT FALSE
);
"""

CREATE_SUBFIELD_COUNTS_VIEW = """
CREATE OR REPLACE VIEW subfield_daily AS
SELECT
    scraped_date,
    unnest(string_split(replace(replace(subfield_tags,'[',''),']',''),',')) AS subfield,
    COUNT(*) AS cnt
FROM jobs
WHERE source != 'reddit'
GROUP BY scraped_date, subfield;
"""


def get_conn(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(db_path))
    conn.execute(CREATE_JOBS_TABLE)
    return conn


def upsert_postings(postings: list, conn: Optional[duckdb.DuckDBPyConnection] = None) -> int:
    """Insert or replace job postings. Returns count of newly inserted rows."""
    import json
    close_conn = conn is None
    if conn is None:
        conn = get_conn()

    inserted = 0
    for p in postings:
        skills_str = json.dumps(p.skills)
        tags_str = json.dumps(p.subfield_tags)
        try:
            conn.execute("""
                INSERT INTO jobs (
                    id, title, company, company_type, location,
                    salary_min, salary_max, salary_tc_min, salary_tc_max,
                    experience_years_min, experience_years_max,
                    skills, subfield_tags, source, url, raw_text,
                    scraped_date, posted_date, is_new
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (id) DO UPDATE SET
                    company_type = excluded.company_type,
                    salary_min = COALESCE(excluded.salary_min, jobs.salary_min),
                    salary_max = COALESCE(excluded.salary_max, jobs.salary_max),
                    experience_years_min = COALESCE(excluded.experience_years_min, jobs.experience_years_min),
                    skills = excluded.skills,
                    subfield_tags = excluded.subfield_tags,
                    is_new = excluded.is_new
            """, [
                p.id, p.title, p.company, p.company_type, p.location,
                p.salary_min, p.salary_max, p.salary_tc_min, p.salary_tc_max,
                p.experience_years_min, p.experience_years_max,
                skills_str, tags_str, p.source, p.url, p.raw_text,
                p.scraped_date, p.posted_date, p.is_new,
            ])
            inserted += 1
        except Exception as e:
            print(f"[DB] Insert error for {p.id}: {e}")

    if close_conn:
        conn.close()
    return inserted


def load_all_jobs(conn: Optional[duckdb.DuckDBPyConnection] = None,
                  exclude_reddit: bool = True) -> pd.DataFrame:
    close_conn = conn is None
    if conn is None:
        conn = get_conn()
    where = "WHERE source != 'reddit'" if exclude_reddit else ""
    df = conn.execute(f"SELECT * FROM jobs {where}").df()
    if close_conn:
        conn.close()
    return df


def load_jobs_with_salary(conn=None) -> pd.DataFrame:
    close_conn = conn is None
    if conn is None:
        conn = get_conn()
    df = conn.execute("""
        SELECT *, (salary_min + salary_max) / 2 AS salary_mid
        FROM jobs
        WHERE source != 'reddit'
          AND salary_min IS NOT NULL
          AND salary_max IS NOT NULL
    """).df()
    if close_conn:
        conn.close()
    return df


def load_reddit_posts(conn=None) -> pd.DataFrame:
    close_conn = conn is None
    if conn is None:
        conn = get_conn()
    df = conn.execute("SELECT * FROM jobs WHERE source = 'reddit'").df()
    if close_conn:
        conn.close()
    return df


def job_count_by_source(conn=None) -> pd.DataFrame:
    close_conn = conn is None
    if conn is None:
        conn = get_conn()
    df = conn.execute("""
        SELECT source, COUNT(*) as count FROM jobs
        WHERE source != 'reddit'
        GROUP BY source
    """).df()
    if close_conn:
        conn.close()
    return df


def daily_trend(conn=None) -> pd.DataFrame:
    close_conn = conn is None
    if conn is None:
        conn = get_conn()
    df = conn.execute("""
        SELECT scraped_date, COUNT(*) as new_jobs
        FROM jobs
        WHERE source != 'reddit'
        GROUP BY scraped_date
        ORDER BY scraped_date
    """).df()
    if close_conn:
        conn.close()
    return df
