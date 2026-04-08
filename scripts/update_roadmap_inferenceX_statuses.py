"""
Populate InferenceX v3 submission statuses from the SA tracker spreadsheet:
https://docs.google.com/spreadsheets/d/17fGM09R1AvRu0OavHYkTAzf_WFGXIbBQ1Iv3BlELKDM/edit?gid=197926646

Source data key (from "Model/FW PICs" tab, Submitted (OSS) + In review columns):
  Kimi K2.5  : H200 submitted, B200 submitted, B300 in review, GB200 in review, H100 todo
  MiniMax 2.5: H100/H200/B200 submitted, B300 in review, GB200/GB300 disagg WIP
  Qwen3.5    : H200/B200 submitted (MTP on/off), B300 in review, GB200 SGLang WIP, GB300 no work
  GLM5       : H200/B200 submitted (MTP-off), B300 in review, GB200 data ready (TRT), GB300 NVFP4 WIP
  DeepSeekV4 : model still confidential/unconfirmed
  DSV3/R1    : B200/B300 config in IBDB no PR; others undecided
  GPTOSS 120B: Done: 1 (H100/H200); B200/B300 config in IBDB; best effort maintenance mode

Status mapping:
  submitted    = Merged / Done
  tuning_wip   = PR ready / In review / Config in IBDB / WIP
  undecided    = No work yet / model unconfirmed
  not_targeting = Not Supporting

Note: H200 results from tracker mapped to H100 in our DB (both Hopper generation).
Both seqlens (1k/1k, 8k/1k) get the same status since tracker doesn't split at seqlen level.

Run from repo root:
    .venv/bin/python3 scripts/update_roadmap_inferenceX_statuses.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.database import SessionLocal
from app.models import BenchmarkSubmission

# (chip, model, status, notes)
# Applied to BOTH seqlens (1k/1k and 8k/1k) for inferenceX-v3
UPDATES = [
    # ── Kimi K2.5 ──────────────────────────────────────────────────────────
    ("H100",  "Kimi K2.5",    "tuning_wip",    "H100 in todo queue; H200 already submitted"),
    ("B200",  "Kimi K2.5",    "submitted",      None),
    ("B300",  "Kimi K2.5",    "tuning_wip",    "In review"),
    ("GB200", "Kimi K2.5",    "tuning_wip",    "In review (TRT-LLM & vLLM)"),
    ("GB300", "Kimi K2.5",    "tuning_wip",    None),

    # ── MiniMax 2.5 ────────────────────────────────────────────────────────
    ("H100",  "MiniMax 2.5",  "submitted",      None),
    ("B200",  "MiniMax 2.5",  "submitted",      None),
    ("B300",  "MiniMax 2.5",  "tuning_wip",    "In review"),
    ("GB200", "MiniMax 2.5",  "tuning_wip",    "Disagg vLLM WIP"),
    ("GB300", "MiniMax 2.5",  "tuning_wip",    "Disagg vLLM WIP"),

    # ── Qwen3.5 397B ───────────────────────────────────────────────────────
    ("H100",  "Qwen3.5 397B", "submitted",      None),
    ("B200",  "Qwen3.5 397B", "submitted",      None),
    ("B300",  "Qwen3.5 397B", "tuning_wip",    "In review (MTP on/off)"),
    ("GB200", "Qwen3.5 397B", "tuning_wip",    "SGLang disagg WIP (FP8); FP4 no work yet"),
    ("GB300", "Qwen3.5 397B", "undecided",      "No work yet"),

    # ── GLM5 ───────────────────────────────────────────────────────────────
    ("H100",  "GLM5",         "submitted",      None),
    ("B200",  "GLM5",         "submitted",      None),
    ("B300",  "GLM5",         "tuning_wip",    "In review (MTP off)"),
    ("GB200", "GLM5",         "tuning_wip",    "GB200 data ready (TRT-LLM); NVFP4 WIP"),
    ("GB300", "GLM5",         "tuning_wip",    "NVFP4 WIP"),

    # ── DeepSeekV4 ─────────────────────────────────────────────────────────
    ("H100",  "DeepSeekV4",   "undecided",      "Model still confidential/unconfirmed"),
    ("B200",  "DeepSeekV4",   "undecided",      "Model still confidential/unconfirmed"),
    ("B300",  "DeepSeekV4",   "undecided",      "Model still confidential/unconfirmed"),
    ("GB200", "DeepSeekV4",   "undecided",      "Model still confidential/unconfirmed"),
    ("GB300", "DeepSeekV4",   "undecided",      "Model still confidential/unconfirmed"),

    # ── DSV3/R1 ────────────────────────────────────────────────────────────
    ("H100",  "DSV3/R1",      "tuning_wip",    None),
    ("B200",  "DSV3/R1",      "tuning_wip",    "Config in IBDB, no PR yet"),
    ("B300",  "DSV3/R1",      "tuning_wip",    "Config in IBDB, no PR yet; B200 > B300 perf"),
    ("GB200", "DSV3/R1",      "undecided",      None),
    ("GB300", "DSV3/R1",      "undecided",      None),

    # ── GPTOSS 120B ────────────────────────────────────────────────────────
    ("H100",  "GPTOSS 120B",  "submitted",      "Best effort maintenance mode"),
    ("B200",  "GPTOSS 120B",  "tuning_wip",    "Config in IBDB, no PR yet; best effort maintenance"),
    ("B300",  "GPTOSS 120B",  "tuning_wip",    "Config in IBDB, no PR yet"),
    ("GB200", "GPTOSS 120B",  "undecided",      "Best effort maintenance; no disagg work yet"),
    ("GB300", "GPTOSS 120B",  "not_targeting",  "Best effort maintenance mode; no disagg planned"),
]

SEQLENS = ["1k/1k", "8k/1k"]
BENCHMARK_VERSION = "inferenceX-v3"


def run():
    db = SessionLocal()
    try:
        updated = 0
        not_found = 0
        for (chip, model, status, notes) in UPDATES:
            for seqlen in SEQLENS:
                row = (
                    db.query(BenchmarkSubmission)
                    .filter_by(
                        benchmark_version=BENCHMARK_VERSION,
                        chip=chip,
                        model=model,
                        seqlen=seqlen,
                    )
                    .first()
                )
                if row is None:
                    print(f"  NOT FOUND: {chip} | {model} | {seqlen}")
                    not_found += 1
                    continue
                row.status = status
                if notes is not None:
                    row.notes = notes
                updated += 1

        db.commit()
        print(f"[update] {updated} rows updated, {not_found} not found")
    finally:
        db.close()


if __name__ == "__main__":
    run()
