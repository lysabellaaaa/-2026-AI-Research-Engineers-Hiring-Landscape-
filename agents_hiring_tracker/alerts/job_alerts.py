"""Job alert system — checkpoint diff to detect new postings each day."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

CHECKPOINTS_DIR = Path(__file__).parent.parent / "data" / "checkpoints"
ALERTS_DIR = Path(__file__).parent.parent / "alerts"


def _checkpoint_path(for_date: Optional[date] = None) -> Path:
    d = for_date or date.today()
    return CHECKPOINTS_DIR / f"checkpoint_{d.isoformat()}.json"


def load_checkpoint(for_date: date) -> set[str]:
    path = _checkpoint_path(for_date)
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("ids", []))


def save_checkpoint(ids: set[str], for_date: Optional[date] = None) -> Path:
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(for_date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": (for_date or date.today()).isoformat(), "ids": list(ids)}, f)
    return path


def get_previous_checkpoint() -> set[str]:
    """Load the most recent checkpoint that isn't today's."""
    today = date.today()
    files = sorted(CHECKPOINTS_DIR.glob("checkpoint_*.json"), reverse=True)
    for f in files:
        try:
            d = date.fromisoformat(f.stem.replace("checkpoint_", ""))
            if d < today:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                return set(data.get("ids", []))
        except Exception:
            continue
    return set()


def detect_new_jobs(postings: list, previous_ids: set[str]) -> list:
    """Mark postings as new if not seen before, return list of new ones."""
    new_jobs = []
    for p in postings:
        if p.id not in previous_ids:
            p.is_new = True
            new_jobs.append(p)
    return new_jobs


def save_alert_log(new_jobs: list, for_date: Optional[date] = None) -> Optional[Path]:
    if not new_jobs:
        return None
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    d = for_date or date.today()
    out = ALERTS_DIR / f"new_jobs_{d.isoformat()}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump([j.to_dict() for j in new_jobs], f, indent=2, default=str)
    return out


def load_latest_alerts() -> list[dict]:
    """Load today's or most recent alert file for the dashboard feed."""
    files = sorted(ALERTS_DIR.glob("new_jobs_*.json"), reverse=True)
    if not files:
        return []
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)
