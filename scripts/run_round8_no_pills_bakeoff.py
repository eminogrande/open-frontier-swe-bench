#!/usr/bin/env python3
"""Round 8: Zero Code-Pill Human ADHD Bakeoff (V8 vs P9a vs P9b).

Reproduces the exact Cloudflare CORS review screenshot (S3) + S1 deploy + H2 JWT coding
across Gemini 4 Neon XHigh/High, Hydrogen High, and Claude Sonnet 5.5 High.
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

r6.TASKS["S3_cloudflare_cors_review"] = {
    "kind": "comm",
    "timeout": 120,
    "files": {
        "review_notes.md": (
            "# Incident Review: Lightning Address CORS Breakage\n"
            "- Commit 1a6e104 (PR #7 by Lennard) already fixed and deployed to production; local main synced.\n"
            "- Live verification: GET 200 and OPTIONS 204 both return Access-Control-Allow-Origin: *.\n"
            "- Root cause: Old Hetzner Nginx (nuri.com.conf) inherited server-level Access-Control-Allow-Origin: * "
            "into /.well-known/lnurlp/ and /lnurl/callback/. During the Cloudflare migration, proxyToArkade() in "
            "worker.mjs only copied the inner location {} directives, bypassed commonHeaders() and OPTIONS preflight, "
            "and had no unit test covering proxy routes.\n"
            "- Future deploy protection: 1a6e104 added a CI regression test in test-worker-cloudflare.mjs "
            "(runs in npm run test:unit and candidate deploy gate) and uses headers.set() to prevent duplicate *, *.\n"
            "- Minor leftover edge case: bare https://nuri.com/.well-known/lnurlp (no username or trailing slash) "
            "still returns 301 to https://arkade.nuri.com/.well-known/lnurlp/ where upstream lacks CORS. "
            "Real LUD-16 /<user> wallet calls are unaffected.\n"
            "- Optional follow-up: rewrite bare arkade.nuri.com Location header and add CHANGELOG.md note, or leave as-is.\n"
        )
    },
    "prompt": (
        "did we break that when we did nuri.com upgrade to cloudflare or is it something different? "
        "ok i think its fixed review review_notes.md and learn and understand what we did wrong, "
        "is there a chance we fuck it up again deploying new nuri versions?"
    ),
    "eval": None,
}


def measure_clutter(text: str) -> dict:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    words = text.split()
    wpl = [len(ln.split()) for ln in lines] if lines else [0]
    pills = len(re.findall(r"`[^`]+`", text))
    file_links = len(re.findall(r"\[[^\]]+\]\(file://", text))
    parens = text.count("(")
    semis = text.count(";")
    # visual noise score: every gray pill, file link, paren, semi, and wrapped >18w line hurts scannability
    long_lines = sum(1 for w in wpl if w > 18)
    clutter_score = pills * 3 + file_links * 4 + parens * 2 + semis * 2 + long_lines * 5
    return {
        "reply_words": len(words),
        "max_line_words": max(wpl),
        "mean_line_words": round(sum(wpl) / max(1, len(wpl)), 1),
        "backtick_pills": pills,
        "file_links": file_links,
        "parens": parens,
        "semicolons": semis,
        "long_lines_gt18w": long_lines,
        "clutter_score": clutter_score,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--models",
        nargs="+",
        default=[
            "Gemini 4 Neon (XHigh)",
            "Gemini 4 Neon (High)",
            "Gemini 4 Hydrogen (High)",
            "Claude Sonnet 5.5 (High)",
        ],
    )
    ap.add_argument("--tasks", nargs="+", default=["S3_cloudflare_cors_review", "S1_deploy_status_reply", "H2_jwt_security"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    variants = {
        "V8_current": (REPO / "prompts/V8_telegraphic_adhd.md").read_text(),
        "P9a_human_no_pills": (REPO / "prompts/round8/P9a_human_no_pills.md").read_text(),
        "P9b_exec_caveman": (REPO / "prompts/round8/P9b_exec_caveman.md").read_text(),
    }

    jobs = [(m, v, t, 1) for m in args.models for v in variants for t in args.tasks]
    print(f"START R8 backend=agy jobs={len(jobs)} workers={args.workers}", flush=True)

    gpath = pathlib.Path.home() / ".gemini/GEMINI.md"
    gemini_bak = gpath.read_text() if gpath.exists() else None
    if gemini_bak is not None:
        gpath.write_text("")

    records = []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(r6.execute_cell, j, variants, "agy", None, out) for j in jobs]
            for f in as_completed(futs):
                rec = f.result()
                rec.update(measure_clutter(rec.get("final_text", "")))
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
            "mean_h2_loc": round(sum(r["code_loc"] for r in swe) / max(1, len(swe)), 1),
            "mean_think_tok": round(sum(r["reasoning_tokens"] for r in vr) / max(1, len(vr))),
            "mean_total_tok": round(sum(r["total_tokens"] for r in vr) / max(1, len(vr))),
            "mean_wall_s": round(sum(r["elapsed_s"] for r in vr) / max(1, len(vr)), 1),
            "comm_words": round(sum(r["reply_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_max_line_w": round(sum(r["max_line_words"] for r in comm) / max(1, len(comm)), 1),
            "comm_pills": round(sum(r["backtick_pills"] for r in comm) / max(1, len(comm)), 1),
            "comm_parens": round(sum(r["parens"] for r in comm) / max(1, len(comm)), 1),
            "comm_semis": round(sum(r["semicolons"] for r in comm) / max(1, len(comm)), 1),
            "comm_clutter": round(sum(r["clutter_score"] for r in comm) / max(1, len(comm)), 1),
        }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("\n=== R8 SUMMARY ===")
    print(json.dumps(summary, indent=2), flush=True)

    print("\n=== S3 CLOUDFLARE CORS SCREENSHOT REPLIES ===")
    for v in variants:
        print(f"\n--- {v} ---")
        for r in [x for x in records if x["variant"] == v and x["task"] == "S3_cloudflare_cors_review" and not x.get("infra_error")]:
            print(f"[{r['model']} | w={r['reply_words']} maxL={r['max_line_words']} pills={r['backtick_pills']} clutter={r['clutter_score']} think={r['reasoning_tokens']}]\n{r['final_text']}\n")


if __name__ == "__main__":
    main()
