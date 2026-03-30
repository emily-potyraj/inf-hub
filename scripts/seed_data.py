#!/usr/bin/env python3
"""
Seed script for inf-hub workloads and team functions.
Run from the worktree root:  python scripts/seed_data.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import TeamFunction, Workload

db = SessionLocal()

# ─── Team Functions ────────────────────────────────────────────────────────────

TEAM_FUNCTIONS = [
    dict(function="VPR",                     owner="Kedar Pandurang Potdar", backup=None,
         notes="oversees InferenceX submissions, point person to interface with SA"),
    dict(function="Product Management",      owner="Nick Comly",             backup=None,
         notes="PM lead; sets scope, priorities, and SA relationship"),
    dict(function="Competitive Analysis",    owner="Edwin Mascarenhas",      backup=None,
         notes="Tracks AMD/competitor submissions; manages IBDB coverage and profiling"),
    dict(function="InfBench / Perf Infra",   owner="Alex Settle",            backup="Xiaoming Chen",
         notes="AIPerf benchmarking infra, srt-slurm, multi-turn harness"),
    dict(function="Dynamo Integration",      owner="Itay Neeman",            backup=None,
         notes="Dynamo disagg orchestration, NIXL integration"),
    dict(function="FlashInfer",              owner="Jingfan Sun",            backup=None,
         notes="FlashInfer kernels; sparse MLA, MoE-A2A"),
    dict(function="TRT-LLM",                owner="Jonas Li",               backup="Pietro Cicotti",
         notes="TRT-LLM configs, SA submission, cuteDSL, A2A perf"),
    dict(function="SGLang",                  owner="Po-Han Huang",           backup="Ankur Singh",
         notes="SGLang agg + disagg configs, NIXL recipes, disagg submission workflow"),
    dict(function="vLLM / Infrastructure",   owner="Xin Li",                 backup=None,
         notes="vLLM framework owner, automation, agentic workflows, scope owner"),
]

existing_fns = {tf.function for tf in db.query(TeamFunction).all()}
added = 0
for row in TEAM_FUNCTIONS:
    if row["function"] not in existing_fns:
        db.add(TeamFunction(**row))
        added += 1
db.commit()
print(f"Team functions: added {added}, skipped {len(TEAM_FUNCTIONS) - added} (already existed)")

# ─── Workloads ─────────────────────────────────────────────────────────────────
# Columns: model, hardware, framework, precision, scenario, seqlens,
#          status, pic, priority, work_type, infmax_submitted, notes

WORKLOADS = [
    # ── Kimi K2.5 1T (Priority 1) ─────────────────────────────────────────────
    # B200 agg — INT4 vLLM — Merged
    ("Kimi-K2.5", "B200",  "vLLM",    "INT4",  "agg",    "1k/1k", "infmax_submitted", "Kaihang Jiang",  1, "tune", "yes", "INT4 B200 merged on SA; FI int4 MoEs"),
    ("Kimi-K2.5", "B200",  "vLLM",    "INT4",  "agg",    "8k/1k", "infmax_submitted", "Kaihang Jiang",  1, "tune", "yes", "INT4 B200 merged on SA"),
    # H200 agg — INT4 vLLM — Merged
    ("Kimi-K2.5", "H200",  "vLLM",    "INT4",  "agg",    "1k/1k", "infmax_submitted", "Xin Li",         1, "tune", "yes", "H200 INT4 merged"),
    ("Kimi-K2.5", "H200",  "vLLM",    "INT4",  "agg",    "8k/1k", "infmax_submitted", "Xin Li",         1, "tune", "yes", "H200 INT4 merged; INT4+Blackwell out of scope"),
    # B200 agg — FP8 vLLM — Merged
    ("Kimi-K2.5", "B200",  "vLLM",    "FP8",   "agg",    "1k/1k", "infmax_submitted", "Kaihang Jiang",  1, "tune", "yes", "B200 FP8 merged on SA"),
    ("Kimi-K2.5", "B200",  "vLLM",    "FP8",   "agg",    "8k/1k", "infmax_submitted", "Kaihang Jiang",  1, "tune", "yes", "B200 FP8 merged on SA"),
    # B200 agg — NVFP4 vLLM — WIP
    ("Kimi-K2.5", "B200",  "vLLM",    "NVFP4", "agg",    "1k/1k", "config_search",    "Hanjie Qiu",     1, "tune", None,  "B200 agg submitted; dynamo 1.0.0 integration working"),
    ("Kimi-K2.5", "B200",  "vLLM",    "NVFP4", "agg",    "8k/1k", "config_search",    "Hanjie Qiu",     1, "tune", None,  "B200 agg submitted"),
    # B200 disagg — NVFP4 vLLM — staged
    ("Kimi-K2.5", "B200",  "vLLM",    "NVFP4", "disagg", "1k/1k", "config_search",    "Hanjie Qiu",     1, "tune", None,  "0.17.1 + dynamo 1.0.0 works; submission staged this week"),
    ("Kimi-K2.5", "B200",  "vLLM",    "NVFP4", "disagg", "8k/1k", "config_search",    "Hanjie Qiu",     1, "tune", None,  "Staged; gap analysis with TRTLLM + cuteDSLMoE ongoing"),
    # B200 disagg — NVFP4 TRT-LLM — initial paretos ready
    ("Kimi-K2.5", "B200",  "TRT-LLM", "NVFP4", "disagg", "1k/1k", "config_search",    "Jonas Li",       1, "tune", None,  "Initial disagg paretos for 1k1k ready"),
    ("Kimi-K2.5", "B200",  "TRT-LLM", "NVFP4", "disagg", "8k/1k", "config_search",    "Jonas Li",       1, "tune", None,  "Initial disagg paretos for 8k1k ready"),
    # B200 agg — FP8 SGLang — in scope
    ("Kimi-K2.5", "B200",  "SGLang",  "FP8",   "agg",    "1k/1k", "not_started",      "Po-Han Huang",   1, "tune", None,  "FP8 SGLang in scope"),
    ("Kimi-K2.5", "B200",  "SGLang",  "FP8",   "agg",    "8k/1k", "not_started",      "Po-Han Huang",   1, "tune", None,  "FP8 SGLang in scope"),
    ("Kimi-K2.5", "H200",  "SGLang",  "FP8",   "agg",    "1k/1k", "not_started",      "Po-Han Huang",   1, "tune", None,  "H200 FP8 SGLang in scope"),
    ("Kimi-K2.5", "H200",  "SGLang",  "FP8",   "agg",    "8k/1k", "not_started",      "Po-Han Huang",   1, "tune", None,  "H200 FP8 SGLang in scope"),
    # B200 agg — FP8 TRT-LLM — in scope
    ("Kimi-K2.5", "B200",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "not_started",      "Shicheng Li",    1, "tune", None,  "TRT-LLM FP8 in scope; A2A perf tech-report out"),
    ("Kimi-K2.5", "B200",  "TRT-LLM", "FP8",   "agg",    "8k/1k", "not_started",      "Shicheng Li",    1, "tune", None,  "TRT-LLM FP8 in scope"),
    ("Kimi-K2.5", "H200",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "not_started",      "Shicheng Li",    1, "tune", None,  "H200 TRT-LLM FP8 in scope"),
    ("Kimi-K2.5", "H200",  "TRT-LLM", "FP8",   "agg",    "8k/1k", "not_started",      "Shicheng Li",    1, "tune", None,  "H200 TRT-LLM FP8 in scope"),
    # GB200 NVL72 disagg — NVFP4 — HIGH PRIORITY
    ("Kimi-K2.5", "GB200", "vLLM",    "NVFP4", "disagg", "1k/1k", "not_started",      "Hanjie Qiu",     1, "tune", None,  "NVFP4 WideEP Disagg on GB200 — priority for 2026-03-25 week"),
    ("Kimi-K2.5", "GB200", "vLLM",    "NVFP4", "disagg", "8k/1k", "not_started",      "Hanjie Qiu",     1, "tune", None,  "NVFP4 WideEP Disagg on GB200 — priority"),
    ("Kimi-K2.5", "GB200", "TRT-LLM", "NVFP4", "disagg", "1k/1k", "not_started",      "Jonas Li",       1, "tune", None,  "NVFP4 WideEP Disagg on GB200 — priority"),
    ("Kimi-K2.5", "GB200", "TRT-LLM", "NVFP4", "disagg", "8k/1k", "not_started",      "Jonas Li",       1, "tune", None,  "NVFP4 WideEP Disagg on GB200 — priority"),
    # B300 in scope
    ("Kimi-K2.5", "B300",  "vLLM",    "NVFP4", "agg",    "1k/1k", "not_started",      "Kaihang Jiang",  1, "tune", None,  "B300 in scope"),
    ("Kimi-K2.5", "B300",  "SGLang",  "FP8",   "agg",    "1k/1k", "not_started",      "Po-Han Huang",   1, "tune", None,  "B300 in scope"),
    ("Kimi-K2.5", "B300",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "not_started",      "Shicheng Li",    1, "tune", None,  "B300 in scope"),

    # ── DSR1 (Priority 2) ──────────────────────────────────────────────────────
    # B200 — SGLang — FP8 — agg + disagg — Merged
    ("DSR1", "B200",  "SGLang",  "FP8",   "agg",    "1k/1k", "infmax_submitted", "Ankur Singh",    2, "tune", "yes", "B200 FP8 agg config merged"),
    ("DSR1", "B200",  "SGLang",  "FP8",   "agg",    "8k/1k", "infmax_submitted", "Ankur Singh",    2, "tune", "yes", "B200 FP8 agg config merged"),
    ("DSR1", "B200",  "SGLang",  "FP8",   "disagg", "1k/1k", "infmax_submitted", "Po-Han Huang",   2, "tune", "yes", "Better FP8 disagg B200 config merged; pending SA data refresh"),
    ("DSR1", "B200",  "SGLang",  "FP8",   "disagg", "8k/1k", "infmax_submitted", "Po-Han Huang",   2, "tune", "yes", "Better FP8 disagg B200 config merged"),
    # B200 — TRT-LLM — FP8 — config in IBDB
    ("DSR1", "B200",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "internal_review",  "Jonas Li",       2, "tune", None,  "Config in IBDB; no PR yet"),
    ("DSR1", "B200",  "TRT-LLM", "FP8",   "agg",    "8k/1k", "internal_review",  "Jonas Li",       2, "tune", None,  "Config in IBDB; no PR yet"),
    # H200 — SGLang — FP8 — disagg — WIP
    ("DSR1", "H200",  "SGLang",  "FP8",   "disagg", "1k/1k", "config_search",    "Ankur Singh",    2, "tune", None,  "Upgrading SGLang v0.5.8.post1→v0.5.9; GB200/GB300 MTP disagg in IBDB"),
    ("DSR1", "H200",  "SGLang",  "FP8",   "disagg", "8k/1k", "config_search",    "Ankur Singh",    2, "tune", None,  "Upgrading SGLang v0.5.8.post1→v0.5.9"),
    # B300 — in scope (configs in IBDB, no PR)
    ("DSR1", "B300",  "SGLang",  "FP8",   "agg",    "1k/1k", "config_search",    "Ankur Singh",    2, "tune", None,  "Config in IBDB, no PR; same perf as B200"),
    ("DSR1", "B300",  "SGLang",  "FP8",   "agg",    "8k/1k", "config_search",    "Ankur Singh",    2, "tune", None,  "Config in IBDB, no PR"),
    ("DSR1", "B300",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "config_search",    "Jonas Li",       2, "tune", None,  "Config in IBDB, no PR"),
    ("DSR1", "B300",  "TRT-LLM", "FP8",   "agg",    "8k/1k", "config_search",    "Jonas Li",       2, "tune", None,  "Config in IBDB, no PR; B200>B300 in high conc region"),
    # GB200 disagg in scope
    ("DSR1", "GB200", "SGLang",  "FP8",   "disagg", "1k/1k", "not_started",      "Po-Han Huang",   2, "tune", None,  "GB200 MTP disagg configs in IBDB"),
    ("DSR1", "GB200", "SGLang",  "FP8",   "disagg", "8k/1k", "not_started",      "Po-Han Huang",   2, "tune", None,  "GB200 MTP disagg configs in IBDB"),

    # ── DeepSeek V4 (Priority 2, waiting for model release) ───────────────────
    ("DeepSeek-V4", "B200",  "vLLM",    "FP8",   "agg", "1k/1k", "not_started", "Ben C",      2, "tune", None, "Waiting for model release; expected when new model drops"),
    ("DeepSeek-V4", "B200",  "vLLM",    "FP8",   "agg", "8k/1k", "not_started", "Ben C",      2, "tune", None, "Waiting for model release"),
    ("DeepSeek-V4", "B200",  "TRT-LLM", "FP8",   "agg", "1k/1k", "not_started", "Jonas Li",   2, "tune", None, "Waiting for model release"),
    ("DeepSeek-V4", "B200",  "TRT-LLM", "FP8",   "agg", "8k/1k", "not_started", "Jonas Li",   2, "tune", None, "Waiting for model release"),
    ("DeepSeek-V4", "H200",  "vLLM",    "FP8",   "agg", "1k/1k", "not_started", "Ben C",      2, "tune", None, "Waiting for model release"),
    ("DeepSeek-V4", "H200",  "TRT-LLM", "FP8",   "agg", "1k/1k", "not_started", "Jonas Li",   2, "tune", None, "Waiting for model release"),

    # ── Qwen3.5 397B (Priority 3) ─────────────────────────────────────────────
    # B200 — SGLang — BF16 / FP8 — Merged
    ("Qwen3.5", "B200",  "SGLang",  "BF16",  "agg",    "1k/1k", "infmax_submitted", "Po-Han Huang",  3, "tune", "yes", "B200 BF16 merged"),
    ("Qwen3.5", "B200",  "SGLang",  "BF16",  "agg",    "8k/1k", "infmax_submitted", "Po-Han Huang",  3, "tune", "yes", "B200 BF16 merged"),
    ("Qwen3.5", "B200",  "SGLang",  "FP8",   "agg",    "1k/1k", "infmax_submitted", "Hao Lu",        3, "tune", "yes", "B200 FP8 merged"),
    ("Qwen3.5", "B200",  "SGLang",  "FP8",   "agg",    "8k/1k", "infmax_submitted", "Hao Lu",        3, "tune", "yes", "B200 FP8 merged"),
    # H200 — SGLang — FP8 — Merged
    ("Qwen3.5", "H200",  "SGLang",  "FP8",   "agg",    "1k/1k", "infmax_submitted", "Harshika",      3, "tune", "yes", "H200 FP8 merged"),
    ("Qwen3.5", "H200",  "SGLang",  "FP8",   "agg",    "8k/1k", "infmax_submitted", "Harshika",      3, "tune", "yes", "H200 FP8 merged"),
    # B200 — SGLang — NVFP4 — PR awaiting SA review
    ("Qwen3.5", "B200",  "SGLang",  "NVFP4", "agg",    "1k/1k", "internal_review",  "Ankur Singh",   3, "tune", None,  "PR ready, awaiting SA review"),
    ("Qwen3.5", "B200",  "SGLang",  "NVFP4", "agg",    "8k/1k", "internal_review",  "Ankur Singh",   3, "tune", None,  "PR ready, awaiting SA review"),
    # B200 — TRT-LLM — FP8 — WIP
    ("Qwen3.5", "B200",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "config_search",    "Guoming Zhang", 3, "tune", None,  "Accuracy verified; WIP: MTP eta EoW, TODO: kv-cache reuse"),
    ("Qwen3.5", "B200",  "TRT-LLM", "FP8",   "agg",    "8k/1k", "config_search",    "Guoming Zhang", 3, "tune", None,  "WIP; pytorch workflow PR in flight"),
    ("Qwen3.5", "H200",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "config_search",    "Guoming Zhang", 3, "tune", None,  "B200 and H200 start with agg"),
    # B200 — SGLang — FP8 — disagg — WIP
    ("Qwen3.5", "B200",  "SGLang",  "FP8",   "disagg", "1k/1k", "config_search",    "Po-Han Huang",  3, "tune", None,  "Disagg runs on IBDB; dynamo issues resolved on side branch; not ready for submission"),
    ("Qwen3.5", "B200",  "SGLang",  "FP8",   "disagg", "8k/1k", "config_search",    "Po-Han Huang",  3, "tune", None,  "Disagg on IBDB; going with NIXL"),
    # B300
    ("Qwen3.5", "B300",  "SGLang",  "FP8",   "agg",    "1k/1k", "not_started",      "Ankur Singh",   3, "tune", None,  "B300 in scope"),
    ("Qwen3.5", "B300",  "SGLang",  "FP8",   "agg",    "8k/1k", "not_started",      "Ankur Singh",   3, "tune", None,  "B300 in scope"),
    ("Qwen3.5", "B300",  "SGLang",  "NVFP4", "agg",    "1k/1k", "not_started",      "Ankur Singh",   3, "tune", None,  "B300 NVFP4 in scope"),

    # ── GLM5 744B (Priority 4) ─────────────────────────────────────────────────
    # B200 / H200 — SGLang — FP8 — Merged
    ("GLM5", "B200",  "SGLang",  "FP8",   "agg",    "1k/1k", "infmax_submitted", "Ankur Singh",    4, "tune", "yes", "B200 FP8 configs merged; ready for review"),
    ("GLM5", "B200",  "SGLang",  "FP8",   "agg",    "8k/1k", "infmax_submitted", "Ankur Singh",    4, "tune", "yes", "B200 FP8 configs merged"),
    ("GLM5", "H200",  "SGLang",  "FP8",   "agg",    "1k/1k", "infmax_submitted", "Po-Han Huang",   4, "tune", "yes", "H200 FP8 merged"),
    ("GLM5", "H200",  "SGLang",  "FP8",   "agg",    "8k/1k", "infmax_submitted", "Po-Han Huang",   4, "tune", "yes", "H200 FP8 merged"),
    # B200 — TRT-LLM — FP8 — no updates
    ("GLM5", "B200",  "TRT-LLM", "FP8",   "agg",    "1k/1k", "not_started",      "Jonas Li",       4, "tune", None,  "No updates"),
    ("GLM5", "B200",  "TRT-LLM", "FP8",   "agg",    "8k/1k", "not_started",      "Jonas Li",       4, "tune", None,  "No updates"),
    # B200 — SGLang — NVFP4 — published, recipes WIP
    ("GLM5", "B200",  "SGLang",  "NVFP4", "agg",    "1k/1k", "config_search",    "Julien Lin",     4, "tune", None,  "NVFP4 published; next step MTPv2; good to submit with better trtllm-gen kernels for sparseMLA"),
    ("GLM5", "B200",  "SGLang",  "NVFP4", "agg",    "8k/1k", "config_search",    "Julien Lin",     4, "tune", None,  "NVFP4 published; recipes WIP"),
    # B200 — TRT-LLM — NVFP4 — multiple PRs in-flight
    ("GLM5", "B200",  "TRT-LLM", "NVFP4", "agg",    "1k/1k", "config_search",    "Pietro Cicotti", 4, "tune", None,  "Multiple PRs in-flight: indexer, fusion; start testing after Freedays"),
    ("GLM5", "B200",  "TRT-LLM", "NVFP4", "agg",    "8k/1k", "config_search",    "Pietro Cicotti", 4, "tune", None,  "Multiple PRs in-flight"),
    # Disagg NVFP4 — PRIMARY FOCUS
    ("GLM5", "B200",  "SGLang",  "NVFP4", "disagg", "1k/1k", "config_search",    "Julien Lin",     4, "tune", None,  "Disagg NVFP4 is primary focus; functional with FlashInfer v0.6.7"),
    ("GLM5", "B200",  "SGLang",  "NVFP4", "disagg", "8k/1k", "config_search",    "Julien Lin",     4, "tune", None,  "Disagg NVFP4 primary focus"),
    ("GLM5", "B200",  "TRT-LLM", "NVFP4", "disagg", "1k/1k", "config_search",    "Pietro Cicotti", 4, "tune", None,  "Disagg NVFP4 primary focus"),
    # B300
    ("GLM5", "B300",  "SGLang",  "FP8",   "agg",    "1k/1k", "not_started",      "Ankur Singh",    4, "tune", None,  "B300 in scope"),
    ("GLM5", "B300",  "TRT-LLM", "NVFP4", "agg",    "1k/1k", "not_started",      "Pietro Cicotti", 4, "tune", None,  "B300 in scope"),

    # ── MiniMax-M2.5 230B (Priority 5) ────────────────────────────────────────
    # B200 / H200 — vLLM — FP8 — Merged
    ("MiniMax-M2.5", "B200",  "vLLM",    "FP8",   "agg", "1k/1k", "infmax_submitted", "Wei Zhao",       5, "tune", "yes", "B200 FP8 merged; AMD also staging new B200 agg"),
    ("MiniMax-M2.5", "B200",  "vLLM",    "FP8",   "agg", "8k/1k", "infmax_submitted", "Wei Zhao",       5, "tune", "yes", "B200 FP8 merged"),
    ("MiniMax-M2.5", "H200",  "vLLM",    "FP8",   "agg", "1k/1k", "infmax_submitted", "Harshika",       5, "tune", "yes", "H200 FP8 merged"),
    ("MiniMax-M2.5", "H200",  "vLLM",    "FP8",   "agg", "8k/1k", "infmax_submitted", "Harshika",       5, "tune", "yes", "H200 FP8 merged"),
    # B200 — vLLM — NVFP4 — waiting for public checkpoint
    ("MiniMax-M2.5", "B200",  "vLLM",    "NVFP4", "agg", "1k/1k", "config_search",    "Zhiyu Cheng",    5, "tune", None,  "Checkpoint in review for publishing; vLLM functional with patch"),
    ("MiniMax-M2.5", "B200",  "vLLM",    "NVFP4", "agg", "8k/1k", "config_search",    "Zhiyu Cheng",    5, "tune", None,  "Waiting for public NVFP4 checkpoint"),
    # B200 — TRT-LLM — FP8 / NVFP4 — not started
    ("MiniMax-M2.5", "B200",  "TRT-LLM", "FP8",   "agg", "1k/1k", "not_started",      "Pietro Cicotti", 5, "tune", None,  "Not started; Pietro Cicotti PIC; trtllm-gen MoE expected in 0.19.0"),
    ("MiniMax-M2.5", "B200",  "TRT-LLM", "FP8",   "agg", "8k/1k", "not_started",      "Pietro Cicotti", 5, "tune", None,  "Not started"),
    ("MiniMax-M2.5", "B200",  "TRT-LLM", "NVFP4", "agg", "1k/1k", "not_started",      "Pietro Cicotti", 5, "tune", None,  "Guidance needed whether submission required"),
    # B300 in scope
    ("MiniMax-M2.5", "B300",  "vLLM",    "FP8",   "agg", "1k/1k", "not_started",      "Wei Zhao",       5, "tune", None,  "B300 in scope"),
    ("MiniMax-M2.5", "B300",  "vLLM",    "NVFP4", "agg", "1k/1k", "not_started",      "Zhiyu Cheng",    5, "tune", None,  "B300 in scope; checkpoint needed"),
    ("MiniMax-M2.5", "GB200", "vLLM",    "FP8",   "agg", "1k/1k", "not_started",      "Wei Zhao",       5, "tune", None,  "GB200 NVL72 in scope"),
    ("MiniMax-M2.5", "GB200", "vLLM",    "NVFP4", "agg", "1k/1k", "not_started",      "Zhiyu Cheng",    5, "tune", None,  "GB200 NVL72 in scope"),

    # ── GPT-OSS 120B (Priority 3) ─────────────────────────────────────────────
    ("GPT-OSS", "B200",  "vLLM",    "NVFP4", "agg", "1k/1k", "config_search",    "Jatin Gangani",  3, "tune", None, "Config in IBDB, no PR; same perf as B200"),
    ("GPT-OSS", "B200",  "vLLM",    "NVFP4", "agg", "8k/1k", "config_search",    "Jatin Gangani",  3, "tune", None, "Config in IBDB, no PR"),
    ("GPT-OSS", "B200",  "TRT-LLM", "NVFP4", "agg", "1k/1k", "config_search",    "Jonas Li",       3, "tune", None, "Config in IBDB, no PR; B200>B300 in high conc region"),
    ("GPT-OSS", "B200",  "TRT-LLM", "NVFP4", "agg", "8k/1k", "config_search",    "Jonas Li",       3, "tune", None, "Config in IBDB, no PR"),
    ("GPT-OSS", "B300",  "vLLM",    "NVFP4", "agg", "1k/1k", "not_started",      "Jatin Gangani",  3, "tune", None, "B300 in scope; B200>B300"),
    ("GPT-OSS", "B300",  "TRT-LLM", "NVFP4", "agg", "1k/1k", "not_started",      "Jonas Li",       3, "tune", None, "B300 in scope"),
]

# Get existing workload identity set to skip duplicates
existing_keys = {
    (w.model, w.hardware, w.framework, w.precision, w.scenario, w.seqlens)
    for w in db.query(Workload).all()
}

added = skipped = 0
for row in WORKLOADS:
    (model, hardware, framework, precision, scenario, seqlens,
     status, pic, priority, work_type, infmax_submitted, notes) = row
    key = (model, hardware, framework, precision, scenario, seqlens)
    if key in existing_keys:
        skipped += 1
        continue
    w = Workload(
        model=model,
        hardware=hardware,
        framework=framework,
        precision=precision,
        scenario=scenario,
        seqlens=seqlens,
        status=status,
        pic=pic,
        priority=priority,
        work_type=work_type,
        infmax_submitted=infmax_submitted,
        notes=notes,
    )
    db.add(w)
    existing_keys.add(key)
    added += 1

db.commit()
print(f"Workloads: added {added}, skipped {skipped} (already existed)")
db.close()
print("Done.")
