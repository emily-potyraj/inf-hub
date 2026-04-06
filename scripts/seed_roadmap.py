"""
Seed script for roadmap benchmark_versions and benchmark_submissions tables.
Idempotent: skips rows that already exist.

Run from the worktree root:
    python3 scripts/seed_roadmap.py
"""
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `app` is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.database import SessionLocal
from app.models import BenchmarkVersion, BenchmarkSubmission


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

VERSIONS = [
    # (benchmark_version, benchmark_group, display_name, is_active, submission_date, publication_date, sort_order)
    ("inferenceX-v3", "inferenceX",          "InferenceX",          1, None, None, 10),
    ("inferenceX-v2", "inferenceX",          "InferenceX",          0, None, None, 20),
    ("inferenceX-v1", "inferenceX",          "InferenceX",          0, None, None, 30),
    ("mlperf-v6.1",   "mlperf",              "MLPerf Inference",    1, None, None, 40),
    ("aa-slt",        "artificial_analysis", "Artificial Analysis", 1, None, None, 50),
    ("aa-agentperf",  "artificial_analysis", "Artificial Analysis", 0, None, None, 60),
]

# Submission combos:
# (benchmark_version, chips, models, seqlens)
SUBMISSION_SETS = [
    (
        "inferenceX-v3",
        ["H100", "B200", "B300", "GB200", "GB300"],
        ["DeepSeekV4", "Kimi K2.5", "Qwen3.5 397B", "GLM5", "MiniMax 2.5", "DSV3/R1", "GPTOSS 120B"],
        ["1k/1k", "8k/1k"],
    ),
    (
        "mlperf-v6.1",
        ["H100", "H200", "B200", "B300", "GB200", "GB300"],
        ["Llama 3.1 405B", "DeepSeek-R1", "GPT-OSS 120B", "Llama 3.1 8B", "Qwen3-VL"],
        ["Offline", "Server"],
    ),
    (
        "aa-slt",
        ["H200", "B200", "GB300"],
        ["GPT-OSS 120B", "Llama 3.3 70B", "DeepSeek V3.2"],
        ["Peak", "Speed"],
    ),
]


def seed():
    db = SessionLocal()
    try:
        # ---- Seed benchmark_versions ----
        versions_added = 0
        for (bv, group, display, is_active, sub_date, pub_date, sort) in VERSIONS:
            existing = db.get(BenchmarkVersion, bv)
            if existing is None:
                db.add(BenchmarkVersion(
                    benchmark_version=bv,
                    benchmark_group=group,
                    display_name=display,
                    is_active=is_active,
                    submission_date=sub_date,
                    publication_date=pub_date,
                    sort_order=sort,
                ))
                versions_added += 1
        db.commit()
        print(f"[seed] benchmark_versions: {versions_added} added, {len(VERSIONS) - versions_added} already existed")

        # ---- Seed benchmark_submissions ----
        submissions_added = 0
        submissions_skipped = 0
        from sqlalchemy.exc import IntegrityError

        for (bv, chips, models, seqlens) in SUBMISSION_SETS:
            for chip in chips:
                for model in models:
                    for seqlen in seqlens:
                        # Check existence via query to avoid PK lookup on composite unique
                        existing = (
                            db.query(BenchmarkSubmission)
                            .filter_by(benchmark_version=bv, chip=chip, model=model, seqlen=seqlen)
                            .first()
                        )
                        if existing is None:
                            db.add(BenchmarkSubmission(
                                benchmark_version=bv,
                                chip=chip,
                                model=model,
                                seqlen=seqlen,
                                status="undecided",
                            ))
                            submissions_added += 1
                        else:
                            submissions_skipped += 1

        db.commit()
        print(f"[seed] benchmark_submissions: {submissions_added} added, {submissions_skipped} already existed")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
