import argparse
import concurrent.futures
import json
from pathlib import Path
import random

import run_round5_prompt_bakeoff as base

OUT = Path("/private/tmp/bench_clean/r5_thinking_bakeoff")
SEED = 20261122


def aggregate(results, judgments):
    scores = {}
    for judgment in judgments:
        if not judgment["judgment"]:
            continue
        for anon, score in judgment["judgment"].get("scores", {}).items():
            cid = judgment["mapping"].get(anon)
            if cid:
                scores[cid] = score.get("total_100")
    grouped = {}
    for row in results:
        if row.get("infra_error"):
            continue
        key = f"{row['variant']}__{row['thinking_effort']}"
        grouped.setdefault(key, []).append(row)
    summary = {}
    for key, rows in grouped.items():
        passes = sum(r["passed"] for r in rows)
        pass_rate = passes / len(rows)
        mean_tokens = sum(r["total_tokens"] for r in rows) / len(rows)
        mean_wall = sum(r["elapsed_s"] for r in rows) / len(rows)
        blind = [scores[r["id"]] for r in rows if scores.get(r["id"]) is not None]
        summary[key] = {
            "runs": len(rows), "passes": passes, "pass_rate": pass_rate,
            "mean_total_tokens": round(mean_tokens, 1),
            "mean_output_tokens": round(sum(r["output_tokens"] for r in rows) / len(rows), 1),
            "mean_wall_s": round(mean_wall, 2),
            "mean_code_loc": round(sum(r["code_loc"] for r in rows) / len(rows), 1),
            "mean_visible_words": round(sum(len(r["final_text"].split()) for r in rows) / len(rows), 1),
            "expected_tokens_per_pass": round(mean_tokens / pass_rate, 1) if pass_rate else None,
            "expected_wall_s_per_pass": round(mean_wall / pass_rate, 2) if pass_rate else None,
            "mean_blind_score": round(sum(blind) / len(blind), 2) if blind else None,
        }
    output = {"model": base.MODEL, "seed": SEED, "arms": summary}
    (OUT / "summary.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="*", default=["V4a_tldr_caveman", "V4c_adaptive_effort"])
    parser.add_argument("--efforts", nargs="*", default=["low", "high", "max"], choices=["low", "high", "max"])
    parser.add_argument("--tasks", nargs="*", default=list(base.TASKS), choices=list(base.TASKS))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()
    base.VARIANTS["V4c_adaptive_effort"] = (base.REPO / "prompts/V4c_adaptive_effort.md").read_text()
    if any(v not in base.VARIANTS for v in args.variants):
        raise SystemExit(f"Unknown variants: {args.variants}")
    base.OUT = OUT
    base.VARIANTS = {k: v for k, v in base.VARIANTS.items() if k in args.variants}
    OUT.mkdir(parents=True, exist_ok=True)
    base.BASE_SYSTEM_TEMPLATE = (OUT / "base_system_snapshot.md").read_text()
    jobs = [
        (v, t, r, e)
        for v in base.VARIANTS for t in args.tasks
        for r in range(1, args.repetitions + 1) for e in args.efforts
    ]
    random.Random(SEED).shuffle(jobs)
    completed = {}
    results_file = OUT / "results.jsonl"
    if results_file.exists():
        for line in results_file.read_text().splitlines():
            old = json.loads(line)
            if old.get("rc") in (0, -1) and not old.get("infra_error"):
                completed[(old["variant"], old["task"], old["repetition"], old["thinking_effort"])] = old
    pending = [job for job in jobs if job not in completed]
    print(f"THINKING_RESUME valid={len(completed)} pending={len(pending)}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        fresh = list(pool.map(base.run_cell, pending))
    results = [completed[job] for job in jobs if job in completed] + fresh
    with open(OUT / "results_final.jsonl", "w") as handle:
        for result in results:
            handle.write(json.dumps(result) + "\n")
    judgments = []
    if not args.skip_judge:
        for task_id in args.tasks:
            rows = [r for r in results if r["task"] == task_id and not r.get("infra_error")]
            judgments.append(base.judge_task(task_id, rows))
    aggregate(results, judgments)
