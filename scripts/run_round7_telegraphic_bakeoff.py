#!/usr/bin/env python3
"""Round 7: Telegraphic Caveman + ADHD Zero-Filler Bakeoff (V7 vs P8a/P8b/P8c).

Tests whether one-shot telegraphic fragments eliminate long English sentences
without triggering XHigh overthinking or hurting coding accuracy.
"""
import argparse
import json
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import run_round6_frontier_prompt_bench as r6  # noqa: E402

# Add S2: rambling, chatty, multi-question prompt to test anti-mirroring + numbered feedback
r6.TASKS["S2_rambling_chat"] = {
    "kind": "comm",
    "timeout": 120,
    "files": {
        "status.md": (
            "# Service State\n"
            "- api-gateway: healthy, v2.14.0, p99=42ms\n"
            "- worker-billing: 3 failed jobs due to Stripe webhook timeout (retry queue active, no data loss)\n"
            "- cache-redis: memory at 89% (eviction policy allkeys-lru, recommended bump 2GB -> 4GB)\n"
            "- pending PR #418: upgrades Node 22 -> 24, CI green, needs manual approve\n"
        )
    },
    "prompt": (
        "hey so i was wondering where we are with the servers right now, like is anything broken or "
        "burning down, and also i remember there was a redis memory thing or a PR waiting on me, "
        "honestly i have 20 things in my head right now just check status.md and tell me what matters "
        "and what i should actually do first"
    ),
    "eval": None,
}

ARTICLES_FILLER = re.compile(
    r"\b(a|an|the|just|really|basically|actually|simply|certainly|however|therefore|additionally|overall|in order to|if you want)\b",
    re.I,
)


def measure_telegraphic(text: str) -> dict:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    words = text.split()
    non_tbl_lines = [ln for ln in lines if not ln.startswith("|")]
    wpl = [len(ln.split()) for ln in non_tbl_lines] if non_tbl_lines else [0]
    filler_hits = len(ARTICLES_FILLER.findall(text))
    numbered = sum(1 for ln in lines if re.match(r"^\d+\.\s", ln))
    bold_colon = len(re.findall(r"\*\*[^*]+:\*\*", text))
    return {
        "reply_words": len(words),
        "max_line_words": max(wpl),
        "mean_line_words": round(sum(wpl) / max(1, len(wpl)), 1),
        "filler_article_hits": filler_hits,
        "numbered_items": numbered,
        "bold_colon_fluff": bold_colon,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["agy", "pi"], required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--tasks", nargs="+", default=["S1_deploy_status_reply", "S2_rambling_chat", "H2_jwt_security"])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    variants = {
        "V7_current": (REPO / "prompts/V7_adhd_scannable.md").read_text(),
        "P8a_rules_telegraphic": (REPO / "prompts/round7/P8a_rules_telegraphic.md").read_text(),
        "P8b_oneshot_telegraphic": (REPO / "prompts/round7/P8b_oneshot_telegraphic.md").read_text(),
        "P8c_ultra_oneshot": (REPO / "prompts/round7/P8c_ultra_oneshot.md").read_text(),
    }

    router_key = r6.resolve_router_key() if args.backend == "pi" else None
    existing = {}
    res_log = out / "results.jsonl"
    if res_log.exists():
        for ln in res_log.read_text().splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            if not r.get("infra_error"):
                existing[(r["model"], r["variant"], r["task"])] = r
    all_jobs = [(m, v, t, 1) for m in args.models for v in variants for t in args.tasks]
    jobs = [j for j in all_jobs if (j[0], j[1], j[2]) not in existing]
    print(f"START R7 backend={args.backend} done={len(existing)} pending={len(jobs)} workers={args.workers}", flush=True)

    gemini_bak = None
    if args.backend == "agy" and jobs:
        gpath = pathlib.Path.home() / ".gemini/GEMINI.md"
        if gpath.exists():
            gemini_bak = gpath.read_text()
            gpath.write_text("")

    records = []
    for r in existing.values():
        r.update(measure_telegraphic(r.get("final_text", "")))
        records.append(r)
    try:
        if jobs:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = [ex.submit(r6.execute_cell, j, variants, args.backend, router_key, out) for j in jobs]
                for f in as_completed(futs):
                    rec = f.result()
                    rec.update(measure_telegraphic(rec.get("final_text", "")))
                    records.append(rec)
    finally:
        if gemini_bak is not None:
            (pathlib.Path.home() / ".gemini/GEMINI.md").write_text(gemini_bak)

    (out / "results_final.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")

    summary = {}
    for v in variants:
        vr = [r for r in records if r["variant"] == v and not r.get("infra_error")]
        swe = [r for r in vr if r["task"] == "H2_jwt_security"]
        comm = [r for r in vr if r["task"] != "H2_jwt_security"]
        summary[v] = {
            "runs": len(vr),
            "prompt_chars": vr[0]["prompt_chars"] if vr else 0,
            "prompt_est_tokens": vr[0]["prompt_est_tokens"] if vr else 0,
            "h2_pass": f"{sum(1 for r in swe if r['passed'])}/{len(swe)}",
            "mean_h2_loc": round(sum(r["code_loc"] for r in swe) / max(1, len(swe)), 1),
            "mean_think_tok": round(sum(r["reasoning_tokens"] for r in vr) / max(1, len(vr))),
            "mean_total_tok": round(sum(r["total_tokens"] for r in vr) / max(1, len(vr))),
            "mean_wall_s": round(sum(r["elapsed_s"] for r in vr) / max(1, len(vr)), 1),
            "comm_words": round(sum(r["reply_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_max_line_w": round(sum(r["max_line_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_mean_line_w": round(sum(r["mean_line_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_filler_hits": round(sum(r["filler_article_hits"] for r in comm) / max(1, len(comm)), 1),
            "comm_bold_fluff": round(sum(r["bold_colon_fluff"] for r in comm) / max(1, len(comm)), 1),
            "comm_numbered": round(sum(r["numbered_items"] for r in comm) / max(1, len(comm)), 1),
            "comm_soup": round(sum(r["robot_soup_penalty"] for r in comm) / max(1, len(comm)), 1),
        }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2), flush=True)

    print("\n=== SAMPLE S2 REPLIES ===")
    for v in variants:
        print(f"\n--- {v} ---")
        for r in [x for x in records if x["variant"] == v and x["task"] == "S2_rambling_chat" and not x.get("infra_error")]:
            print(f"[{r['model']} | w={r['reply_words']} maxL={r['max_line_words']} fill={r['filler_article_hits']} think={r['reasoning_tokens']}]\n{r['final_text']}\n")


if __name__ == "__main__":
    main()
