#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.beta_mp4_usage import BETA_DB, BETA_ROOT, ensure_mp4_usage_table, probe_mp4

CANDIDATES = {
    "archive": ("output/browser/browser_final.mp4", "output/final.mp4"),
    "shortform": ("output/shortform/shortform_final.mp4",),
}

def iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = {"mode": "apply" if args.apply else "dry-run", "candidates": [], "inserted": 0, "skipped": 0, "errors": []}
    with sqlite3.connect(BETA_DB, timeout=30) as db:
        db.row_factory = sqlite3.Row
        ensure_mp4_usage_table(db)
        jobs = db.execute("SELECT beta_job_id, owner_user_id, created_at FROM beta_jobs ORDER BY created_at").fetchall()
        for job in jobs:
            job_id = str(job["beta_job_id"])
            owner = job["owner_user_id"]
            job_dir = BETA_ROOT / "data" / "jobs" / job_id
            for output_type, rels in CANDIDATES.items():
                existing = db.execute("SELECT 1 FROM beta_mp4_usage WHERE beta_job_id=? AND output_type=?", (job_id, output_type)).fetchone()
                if existing:
                    report["skipped"] += 1
                    continue
                path = next((job_dir / rel for rel in rels if (job_dir / rel).is_file()), None)
                if path is None:
                    continue
                try:
                    meta = probe_mp4(path)
                    created_at = iso_mtime(path)
                    relative_path = str(path.resolve().relative_to(BETA_ROOT.resolve()))
                    item = {"beta_job_id": job_id, "owner_user_id": owner, "output_type": output_type, "path": relative_path, "created_at": created_at, **meta}
                    report["candidates"].append(item)
                    if args.apply:
                        now = datetime.now(timezone.utc).isoformat()
                        db.execute("""
                            INSERT INTO beta_mp4_usage (
                              beta_job_id, owner_user_id, output_type, mp4_status, mp4_verified,
                              mp4_size_bytes, mp4_duration_seconds, mp4_width, mp4_height, mp4_codec,
                              mp4_relative_path, mp4_validation_result, mp4_created_at, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(beta_job_id, output_type) DO NOTHING
                        """, (job_id, owner, output_type, meta["mp4_status"], meta["mp4_verified"],
                              meta["mp4_size_bytes"], meta["mp4_duration_seconds"], meta["mp4_width"], meta["mp4_height"], meta["mp4_codec"],
                              relative_path, "verified_backfill", created_at, now, now))
                        report["inserted"] += int(db.execute("SELECT changes()").fetchone()[0])
                except Exception as exc:
                    report["errors"].append({"beta_job_id": job_id, "output_type": output_type, "error": str(exc)})
        if args.apply:
            db.commit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
