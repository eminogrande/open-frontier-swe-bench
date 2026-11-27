#!/usr/bin/env python3
"""Round 9: Atomic Numbered Lines Bakeoff (V9 max-3 vs V10 atomic-unlimited).

Reproduces session 9330b5f6 step=492 (7 completed draft updates + 2 open founder calls)
plus S3 Cloudflare review and H2 JWT coding across Hydrogen XHigh, Neon High, Sonnet 5.5 High.
"""
import json
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import run_round6_frontier_prompt_bench as r6  # noqa: E402
import run_round8_no_pills_bakeoff as r8  # noqa: E402

r6.TASKS["S4_blogpost_update"] = {
    "kind": "comm",
    "timeout": 150,
    "files": {
        "draft_notes.md": (
            "# Draft Update Summary (already written to blogpost_draft.md, 5438 words, all checks green)\n"
            "Completed updates already in the draft:\n"
            "- Added honest corporate acquisition under register number HRB 270788 B\n"
            "- Added Striga pullout timing ahead of Lightspark and Bitwala irony\n"
            "- Added Gnosis June pricing notice\n"
            "- Added November bank transfer rejections\n"
            "- Added Paul Miller and Safe cryptographic building blocks\n"
            "- Removed uncapped safe wording\n"
            "- Passed all factual and style checks across 5,438 words\n\n"
            "Open CEO calls needed before locking English post for publishing & translations:\n"
            "1. Private outreach note to Jan Goslicki and his short reply: keep in article or cut?\n"
            "2. Naming Wirex directly on November bank transfer rejections while they are still your live card partner: keep direct name or soften?\n"
            "3. Publish English post right after those calls, or hold for one final read?\n"
        )
    },
    "prompt": (
        "Read draft_notes.md. Assume you just finished saving those edits to blogpost_draft.md. "
        "Send me the chat reply updating me and asking what is still open or unclear from me."
    ),
    "eval": None,
}


def measure_atomic(text: str) -> dict:
    m = r8.measure_clutter(text)
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    num_lines = [ln for ln in lines if re.match(r"^\d+\.\s", ln)]
    num_words = [len(ln.split()) for ln in num_lines] if num_lines else [0]
    max_commas_in_line = max((ln.count(",") for ln in num_lines), default=0)
    merged_next = any(re.match(r"^\d+\.\s.*Next:", ln) for ln in lines)
    has_pick = bool(re.search(r"\b(my pick|pick:|recommend|suggest)", text, re.I))
    m.update({
        "numbered_count": len(num_lines),
        "max_numbered_words": max(num_words),
        "mean_numbered_words": round(sum(num_words) / max(1, len(num_words)), 1),
        "max_commas_in_line": max_commas_in_line,
        "merged_next_bug": merged_next,
        "has_recommendation": has_pick,
    })
    return m


def main():
    out = REPO / ".bench_work/r9_atomic"
    out.mkdir(parents=True, exist_ok=True)
    models = [
        "Gemini 4 Hydrogen (XHigh)",
        "Gemini 4 Neon (High)",
        "Claude Sonnet 5.5 (High)",
    ]
    tasks = ["S4_blogpost_update", "S3_cloudflare_cors_review", "H2_jwt_security"]
    variants = {
        "V9_max3": (REPO / "prompts/V9_adhd_founder.md").read_text(),
        "V10_atomic": (REPO / "prompts/round9/P10_atomic_founder.md").read_text(),
    }
    jobs = [(m, v, t, 1) for m in models for v in variants for t in tasks]
    print(f"START R9 backend=agy jobs={len(jobs)} workers=6", flush=True)

    gpath = pathlib.Path.home() / ".gemini/GEMINI.md"
    gemini_bak = gpath.read_text() if gpath.exists() else None
    if gemini_bak is not None:
        gpath.write_text("")

    records = []
    try:
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(r6.execute_cell, j, variants, "agy", None, out) for j in jobs]
            for f in as_completed(futs):
                rec = f.result()
                rec.update(measure_atomic(rec.get("final_text", "")))
                records.append(rec)
    finally:
        if gemini_bak is not None:
            gpath.write_text(gemini_bak)

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
            "mean_think_tok": round(sum(r["reasoning_tokens"] for r in vr) / max(1, len(vr))),
            "mean_total_tok": round(sum(r["total_tokens"] for r in vr) / max(1, len(vr))),
            "mean_wall_s": round(sum(r["elapsed_s"] for r in vr) / max(1, len(vr)), 1),
            "comm_words": round(sum(r["reply_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_max_num_w": round(sum(r["max_numbered_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_mean_num_w": round(sum(r["mean_numbered_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_max_commas": round(sum(r["max_commas_in_line"] for r in comm) / max(1, len(comm)), 1),
            "comm_pills": round(sum(r["backtick_pills"] for r in comm) / max(1, len(comm)), 1),
            "comm_clutter": round(sum(r["clutter_score"] for r in comm) / max(1, len(comm)), 1),
            "merged_next_bugs": sum(1 for r in comm if r["merged_next_bug"]),
            "has_pick_rate": f"{sum(1 for r in comm if r['has_recommendation'])}/{len(comm)}",
        }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("\n=== R9 SUMMARY ===")
    print(json.dumps(summary, indent=2), flush=True)
    print("\n=== S4 BLOGPOST UPDATE REPLIES ===")
    for v in variants:
        print(f"\n--- {v} ---")
        for r in [x for x in records if x["variant"] == v and x["task"] == "S4_blogpost_update" and not x.get("infra_error")]:
            print(f"[{r['model']} | w={r['reply_words']} maxNumW={r['max_numbered_words']} commas={r['max_commas_in_line']} pills={r['backtick_pills']} think={r['reasoning_tokens']}]\n{r['final_text']}\n")


if __name__ == "__main__":
    main()
