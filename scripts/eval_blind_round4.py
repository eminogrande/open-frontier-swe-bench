import os, sys, json, random, shutil, tempfile, subprocess

WORK_R4 = "/tmp/subtasks/st7_round4"
WORK_ST3 = "/tmp/subtasks/st3_gold"
WORK_ST4 = "/tmp/subtasks/st4_bakeoff"
MODELS_JSON = f"{WORK_ST4}/models.json"
V3_SKILL = open("/Users/eminmahrt/Developer/agent-prompt-brevity-bench/prompts/V3_caveman_adhd_winner.md").read()

st4_src = open("/tmp/subtasks/eval_blind_st4.py").read()
gate_defs = st4_src.split('cids = [')[0]
ns = {}
exec(gate_defs, ns)
run_deterministic_gates = ns["run_deterministic_gates"]

def evaluate_round4(cids):
    gate_results = {}
    gate_results["CLOSED_FRONTIER_GOLD_carbon_fable"] = run_deterministic_gates(f"{WORK_ST3}/gold-wt")
    for cid in cids:
        wt = f"{WORK_R4}/wt_{cid}"
        print(f"Running 7 deterministic gates on {cid}...", flush=True)
        gate_results[cid] = run_deterministic_gates(wt)
        print(f"  -> {cid}: {gate_results[cid]['gates_passed']}/{gate_results[cid]['gates_total']}", flush=True)

    rng = random.Random(2026111904)
    shuffled = list(cids)
    rng.shuffle(shuffled)
    anon_map = {f"CANDIDATE_{chr(65+i)}": cid for i, cid in enumerate(shuffled)}
    json.dump(anon_map, open(f"{WORK_R4}/blind_key_mapping.json", "w"), indent=2)

    gold_patch = open(f"{WORK_ST3}/gold_final.patch").read()
    task_spec = open(f"{WORK_ST3}/TASK_PROMPT.md").read()

    bundle_parts = []
    for anon_id in sorted(anon_map.keys()):
        cid = anon_map[anon_id]
        patch = open(f"{WORK_R4}/{cid}.patch").read()
        g = gate_results[cid]
        g_clean = {k: v for k, v in g.items() if k.startswith("G") and isinstance(v, bool)}
        bundle_parts.append(
            f"## {anon_id}\n"
            f"Deterministic Gate Pass Summary: {g['gates_passed']}/{g['gates_total']} ({json.dumps(g_clean)})\n"
            f"```diff\n{patch[:24000] if patch.strip() else '(EMPTY DIFF)'}\n```\n"
        )

    cand_keys_schema = ",\n    ".join(
        f'"{ak}": {{"correctness_25": int, "security_25": int, "craft_brevity_25": int, "tests_docs_25": int, "total_100": int, "key_strengths": string, "flaws_found": string}}'
        for ak in sorted(anon_map.keys())
    )

    blind_prompt = f"""You are a double-blind software-engineering evaluation judge (`Fable`).
{len(cids)} anonymized open-model engineering pipelines (`CANDIDATE_A` through `CANDIDATE_{chr(64+len(cids))}` — model, harness, and parallel topology identities are hidden and randomized) attempted the exact same task on `nuri-server-musig2-v4-arkade` at frozen commit `136a54fa`.

Grade each candidate strictly against the Task Specification, the 7 Deterministic Gate results, and the Closed-Frontier Gold Reference PR (anchor = `95/100`, `7/7` gates) on 4 axes (`0-25` points each, total `0-100`). A candidate MAY score `>95` ONLY if it strictly surpasses the Gold Reference in security hardening, protocol precision, and craft/brevity!
- `correctness_25`: Protocol accuracy (4-leaf `NuriDelegatedVtxo` artifact, RFC-8785 JCS SHA-256 ID in `nuri_renew.json`, minimal CScriptNum + BIP-68 CSV `seconds % 512 === 0` & bit-22, executor REST contract)
- `security_25`: Strict passkey->MuSig2 wallet ownership binding (`deriveAggregatedPk33`, `clientPk33`, `recoveryStore` consistency), cross-user IDOR prevention on `register` & `status`, purpose-scoped token rejection, `outcome_unknown: true` classification, `redirect: "error"`, port `:7081` / `/v1/admin` guards, zero URL/secret leaks
- `craft_brevity_25`: Reuse of existing `ArkadeServer.js` helpers, minimal clean code without bloat/abstractions, zero regressions
- `tests_docs_25`: Depth/realism of `ArkadeExecutorClient.test.js` (including live HTTP auth/IDOR/spoofing tests) and crisp `ENDPOINTS.md` docs

### Task Specification
{task_spec}

### Gold Reference Anchor (`95/100`, `7/7` gates)
```diff
{gold_patch[:24000]}
```

### Anonymized Candidates
{"".join(bundle_parts)}

Return STRICT JSON ONLY:
{{
  "ranking": ["CANDIDATE_...", ...],
  "scores": {{
    {cand_keys_schema}
  }},
  "overall_winner_blind": "CANDIDATE_...",
  "beat_gold_95": ["CANDIDATE_...", ...],
  "synthesis": "3 crisp sentences explaining what separated top candidates and whether any beat the 95/100 Gold anchor."
}}"""

    ag = tempfile.mkdtemp(prefix="r4-fable-")
    try:
        shutil.copy(MODELS_JSON, f"{ag}/models.json")
        open(f"{ag}/settings.json", "w").write("{}")
        open(f"{ag}/trust.json", "w").write("{}")
        open(f"{ag}/APPEND_SYSTEM.md", "w").write(V3_SKILL)
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = ag
        cmd = [
            "/Users/eminmahrt/.local/bin/pi", "-p", "--mode", "json", "--no-session", "--no-context-files",
            "--no-extensions", "--no-mcp", "--no-skills", "--no-tools",
            "--provider", "nous", "--model", "anthropic/claude-fable-5.2", "--thinking", "max",
            "--", blind_prompt
        ]
        print("Running blind Fable 5.2 judge on Round 4...", flush=True)
        proc = subprocess.run(cmd, cwd=WORK_R4, env=env, capture_output=True, text=True, timeout=420)
        final_txt = ""
        for line in proc.stdout.splitlines():
            if not line.strip().startswith("{"): continue
            try: ev = json.loads(line)
            except Exception: continue
            if ev.get("type") == "turn_end":
                txts = [c.get("text", "") for c in ev.get("message", {}).get("content", []) if c.get("type") == "text"]
                if txts: final_txt = "\n".join(txts)
        open(f"{WORK_R4}/fable_blind_judgment_raw.txt", "w").write(final_txt)
        out = {"anon_map": anon_map, "gates": gate_results, "fable_raw": final_txt}
        json.dump(out, open(f"{WORK_R4}/final_blind_evaluation.json", "w"), indent=2)
        print("ROUND 4 BLIND EVAL DONE")
    finally:
        shutil.rmtree(ag, ignore_errors=True)

if __name__ == "__main__":
    raw = json.load(open(f"{WORK_R4}/round4_pipelines_raw.json"))
    evaluate_round4([r["id"] for r in raw])
