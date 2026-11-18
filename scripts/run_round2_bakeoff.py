import os, sys, json, time, shutil, tempfile, subprocess, concurrent.futures

WORK_R2 = "/tmp/subtasks/st5_round2"
WORK_ST3 = "/tmp/subtasks/st3_gold"
WORK_ST4 = "/tmp/subtasks/st4_bakeoff"
NURI_REPO = "/Users/eminmahrt/Developer/nuri-server-musig2-v4-arkade"
ORIGIN_SHA = "136a54faa0c1af817cf9f829412582291a7ec83f"

os.makedirs(WORK_R2, exist_ok=True)
os.makedirs("/tmp/subtasks/logs", exist_ok=True)
LOG = open("/tmp/subtasks/logs/st5_round2.log", "w", buffering=1)

V3_SKILL = open("/Users/eminmahrt/Developer/agent-prompt-brevity-bench/prompts/V3_caveman_adhd_winner.md").read()
TASK_PROMPT = open(f"{WORK_ST3}/TASK_PROMPT.md").read()

# Build isolated models.json for Round 2 using Nous inference gateway (never written to git!)
nous_cfg = json.load(open(f"{WORK_ST4}/models.json"))["providers"]["nous"]
R2_MODELS = [
    ("qwen/qwen4-max", True),
    ("qwen/qwen3.8-2.4t-a95b", True),
    ("mistralai/mistral-large-4-0", True),
    ("mistralai/devstral-2512", False),
    ("meta/muse-spark-open", True),
    ("deepseek/deepseek-v4-pro-0813", True),
    ("deepseek/deepseek-v4.1-flash-1017", True),
    ("moonshotai/kimi-k3.1-pro", True),
    ("z-ai/glm-5.3-prime", True),
    ("minimax/minimax-m3.1-flash", True),
    ("tencent/hy4", True),
    ("anthropic/claude-fable-5.2", True),
]
MODELS_DOC = {
    "providers": {
        "nous": {
            "baseUrl": nous_cfg["baseUrl"],
            "apiKey": nous_cfg["apiKey"],
            "api": "openai-completions",
            "models": [
                {"id": mid, "name": mid, "reasoning": reas, "input": ["text"], "contextWindow": 262144, "maxTokens": 32768}
                for mid, reas in R2_MODELS
            ]
        }
    }
}
MODELS_JSON = f"{WORK_R2}/models.json"
json.dump(MODELS_DOC, open(MODELS_JSON, "w"), indent=2)
REASONING_MAP = dict(R2_MODELS)

def log(msg):
    LOG.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(msg, flush=True)

def run_pi(model, prompt, cwd, tools=True, timeout=540):
    ag = tempfile.mkdtemp(prefix="pi-r2-")
    try:
        shutil.copy(MODELS_JSON, f"{ag}/models.json")
        open(f"{ag}/settings.json", "w").write("{}")
        open(f"{ag}/trust.json", "w").write("{}")
        open(f"{ag}/APPEND_SYSTEM.md", "w").write(V3_SKILL)
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = ag
        cmd = [
            "pi", "-p", "--mode", "json", "--no-session", "--no-context-files",
            "--no-extensions", "--no-mcp", "--no-skills",
            *([] if tools else ["--no-tools"]),
            "--provider", "nous", "--model", model,
            *(["--thinking", "max"] if REASONING_MAP.get(model, True) else []),
            "--", prompt
        ]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
            rc = proc.returncode
            out_s = proc.stdout
            err_s = proc.stderr[-400:]
        except subprocess.TimeoutExpired as te:
            rc = -1
            out_s = (te.stdout.decode("utf-8", "ignore") if isinstance(te.stdout, bytes) else (te.stdout or ""))
            err_s = f"TIMEOUT after {timeout}s"
        elapsed = round(time.time() - t0, 2)
        tot_tok = in_tok = out_tok = rsn_tok = turns = tool_calls = 0
        final_txt = ""
        for line in out_s.splitlines():
            if not line.strip().startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") == "turn_end":
                turns += 1
                msg = ev.get("message", {})
                u = msg.get("usage", {})
                in_tok += u.get("input", 0) + u.get("cacheRead", 0)
                out_tok += u.get("output", 0)
                rsn_tok += u.get("reasoning", 0)
                tot_tok += u.get("totalTokens", 0)
                tool_calls += len(ev.get("toolResults", []))
                txts = [c.get("text", "") for c in msg.get("content", []) if c.get("type") == "text"]
                if txts:
                    final_txt = "\n".join(txts)
        return {
            "model": model, "rc": rc, "elapsed_s": elapsed, "turns": turns, "tool_calls": tool_calls,
            "total_tokens": tot_tok, "input_tokens": in_tok, "output_tokens": out_tok, "reasoning_tokens": rsn_tok,
            "text": final_txt, "stderr": err_s
        }
    finally:
        shutil.rmtree(ag, ignore_errors=True)

PIPELINES = [
    {
        "id": "R2_C1_solo_mistral_large_4",
        "label": "Solo Open-Weight (Mistral Vibe Engine): mistralai/mistral-large-4-0 (1T/52B)",
        "open_weights": True,
        "mode": "solo",
        "worker": "mistralai/mistral-large-4-0"
    },
    {
        "id": "R2_C2_solo_qwen3_8_2_4t",
        "label": "Solo Open-Weight Flagship: qwen/qwen3.8-2.4t-a95b (2.4T/95B)",
        "open_weights": True,
        "mode": "solo",
        "worker": "qwen/qwen3.8-2.4t-a95b"
    },
    {
        "id": "R2_C3_solo_qwen4_max",
        "label": "Solo Flagship (API-only Qwen4): qwen/qwen4-max",
        "open_weights": False,
        "mode": "solo",
        "worker": "qwen/qwen4-max"
    },
    {
        "id": "R2_C4_solo_muse_spark_open",
        "label": "Solo Open-Weight Coding-Specialist: meta/muse-spark-open (816B/42B)",
        "open_weights": True,
        "mode": "solo",
        "worker": "meta/muse-spark-open"
    },
    {
        "id": "R2_C5_solo_deepseek_v4_pro",
        "label": "Solo Open-Weight Flagship: deepseek/deepseek-v4-pro-0813 (1.6T)",
        "open_weights": True,
        "mode": "solo",
        "worker": "deepseek/deepseek-v4-pro-0813"
    },
    {
        "id": "R2_C6_homo_ml4_4stage",
        "label": "Homogeneous Open-Weight 4-Stage: mistral-large-4-0 x4",
        "open_weights": True,
        "mode": "pipeline",
        "planner": "mistralai/mistral-large-4-0",
        "worker": "mistralai/mistral-large-4-0",
        "reviewer": "mistralai/mistral-large-4-0",
        "orchestrator": "mistralai/mistral-large-4-0"
    },
    {
        "id": "R2_C7_hetero_qwen2_4t_ml4_k3",
        "label": "Hetero Open-Frontier A: Planner qwen3.8-2.4t-a95b -> Worker mistral-large-4-0 -> Reviewer kimi-k3.1-pro -> Orch mistral-large-4-0",
        "open_weights": True,
        "mode": "pipeline",
        "planner": "qwen/qwen3.8-2.4t-a95b",
        "worker": "mistralai/mistral-large-4-0",
        "reviewer": "moonshotai/kimi-k3.1-pro",
        "orchestrator": "mistralai/mistral-large-4-0"
    },
    {
        "id": "R2_C8_hetero_k3_muse_ml4",
        "label": "Hetero Open-Frontier B: Planner kimi-k3.1-pro -> Worker muse-spark-open -> Reviewer mistral-large-4-0 -> Orch muse-spark-open",
        "open_weights": True,
        "mode": "pipeline",
        "planner": "moonshotai/kimi-k3.1-pro",
        "worker": "meta/muse-spark-open",
        "reviewer": "mistralai/mistral-large-4-0",
        "orchestrator": "meta/muse-spark-open"
    },
    {
        "id": "R2_C9_hetero_ml4_ds41_qwen2_4t",
        "label": "Hetero Open-Frontier C: Planner mistral-large-4-0 -> Worker deepseek-v4.1-flash-1017 -> Reviewer qwen3.8-2.4t-a95b -> Orch deepseek-v4.1-flash-1017",
        "open_weights": True,
        "mode": "pipeline",
        "planner": "mistralai/mistral-large-4-0",
        "worker": "deepseek/deepseek-v4.1-flash-1017",
        "reviewer": "qwen/qwen3.8-2.4t-a95b",
        "orchestrator": "deepseek/deepseek-v4.1-flash-1017"
    },
    {
        "id": "R2_C10_hetero_dsv4pro_devstral_glm53",
        "label": "Hetero Open-Frontier D: Planner deepseek-v4-pro-0813 -> Worker devstral-2512 -> Reviewer glm-5.3-prime -> Orch devstral-2512",
        "open_weights": True,
        "mode": "pipeline",
        "planner": "deepseek/deepseek-v4-pro-0813",
        "worker": "mistralai/devstral-2512",
        "reviewer": "z-ai/glm-5.3-prime",
        "orchestrator": "mistralai/devstral-2512"
    }
]

def setup_wt(cid):
    wt = f"{WORK_R2}/wt_{cid}"
    if os.path.exists(wt):
        subprocess.run(["git", "worktree", "remove", "--force", wt], cwd=NURI_REPO)
    subprocess.run(["git", "worktree", "add", "--detach", wt, ORIGIN_SHA], cwd=NURI_REPO, check=True)
    if not os.path.exists(f"{wt}/node_modules"):
        os.symlink("/tmp/subtasks/st2_audit/nuri-server-wt/node_modules", f"{wt}/node_modules")
    return wt

def clean_wt_diff(wt):
    subprocess.run(["git", "add", "-N", "."], cwd=wt)
    subprocess.run(["git", "reset", "-q", "--", "node_modules"], cwd=wt)
    return subprocess.run(["git", "diff", "--", ":!node_modules"], cwd=wt, capture_output=True, text=True).stdout

def run_pipeline(cfg):
    cid = cfg["id"]
    wt = setup_wt(cid)
    log(f"[{cid}] Starting ({cfg['label']})...")
    stages = []
    t_start = time.time()

    if cfg["mode"] == "solo":
        s_work = run_pi(cfg["worker"], TASK_PROMPT, cwd=wt, tools=True, timeout=600)
        s_work["stage"] = "solo_worker"
        stages.append(s_work)
    else:
        plan_prompt = f"""ROLE: Planner / Architect. Do NOT edit files. Inspect only exact relevant lines in `src/ArkadeServer.js`, `src/ArkadeConfig.js`, `src/ArkadeNotifications.js`, `ENDPOINTS.md`, and output a tight atomic implementation blueprint (<350 words) for the Worker covering file edits, exact line numbers/helpers to reuse (`verifyRequestAuth`, `getClientSignerFromToken`, `getDerivedServerPublicKey`, `deriveAggregatedPk33`), JCS SHA-256 IDs, BIP-68 CSV encoding traps, and security checks.

TASK:
{TASK_PROMPT}"""
        s_plan = run_pi(cfg["planner"], plan_prompt, cwd=wt, tools=True, timeout=360)
        s_plan["stage"] = "planner"
        stages.append(s_plan)
        log(f"[{cid}] Planner ({cfg['planner']}) done: {s_plan['total_tokens']} tok, {s_plan['elapsed_s']}s")

        work_prompt = f"""ROLE: Worker. Implement the task completely and run `node --test src/ArkadeExecutorClient.test.js` until green.

PLANNER BLUEPRINT:
{s_plan['text']}

EXACT TASK SPECIFICATION:
{TASK_PROMPT}"""
        s_work = run_pi(cfg["worker"], work_prompt, cwd=wt, tools=True, timeout=540)
        s_work["stage"] = "worker"
        stages.append(s_work)
        log(f"[{cid}] Worker ({cfg['worker']}) done: {s_work['total_tokens']} tok, {s_work['elapsed_s']}s")

        cand_diff = clean_wt_diff(wt)
        test_mid = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt, capture_output=True, text=True, timeout=60)
        rev_prompt = f"""ROLE: Adversarial Security & Protocol Reviewer. You have NO file tools (`--no-tools`); the complete candidate git diff and test output are provided inline below—analyze them directly right now! List ONLY real bugs, security bypasses (ownership/IDOR, purpose-scoped token, admin port `:7081` / `/v1/admin` / HTTP redirect leak, URL/secret leak in logs), encoding errors (`encodeScriptNumHex`, BIP-68 seconds % 512 & bit-22, JCS SHA-256), or missing deliverables. If zero issues, reply `APPROVED_NO_FIXES`.

TASK SPEC:
{TASK_PROMPT}

TEST OUTPUT (rc={test_mid.returncode}):
{(test_mid.stdout + test_mid.stderr)[-2000:]}

GIT DIFF:
```diff
{cand_diff[:38000]}
```"""
        s_rev = run_pi(cfg["reviewer"], rev_prompt, cwd=wt, tools=False, timeout=300)
        s_rev["stage"] = "reviewer"
        stages.append(s_rev)
        log(f"[{cid}] Reviewer ({cfg['reviewer']}) done: {s_rev['total_tokens']} tok, {s_rev['elapsed_s']}s | verdict={s_rev['text'][:80].replace(chr(10),' ')}")

        if "APPROVED_NO_FIXES" not in s_rev["text"] or test_mid.returncode != 0:
            orch_prompt = f"""ROLE: Orchestrator / Finisher. Verify each Reviewer finding below; apply real fixes with minimal code changes and ensure `node --test src/ArkadeExecutorClient.test.js` exits 0.

REVIEWER FINDINGS:
{s_rev['text']}"""
            s_orch = run_pi(cfg["orchestrator"], orch_prompt, cwd=wt, tools=True, timeout=360)
            s_orch["stage"] = "orchestrator_fix"
            stages.append(s_orch)
            log(f"[{cid}] Orchestrator ({cfg['orchestrator']}) done: {s_orch['total_tokens']} tok, {s_orch['elapsed_s']}s")

    wall_s = round(time.time() - t_start, 2)
    final_diff = clean_wt_diff(wt)
    open(f"{WORK_R2}/{cid}.patch", "w").write(final_diff)

    test_f = f"{wt}/src/ArkadeExecutorClient.test.js"
    if os.path.exists(test_f):
        own_t = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt, capture_output=True, text=True, timeout=60)
        own_ok = (own_t.returncode == 0)
    else:
        own_ok = False
    added_loc = sum(1 for l in final_diff.splitlines() if l.startswith("+") and not l.startswith("+++") and l[1:].strip())

    res = {
        "id": cid,
        "label": cfg["label"],
        "open_weights": cfg["open_weights"],
        "mode": cfg["mode"],
        "wall_s": wall_s,
        "total_tokens": sum(s["total_tokens"] for s in stages),
        "output_tokens": sum(s["output_tokens"] for s in stages),
        "reasoning_tokens": sum(s["reasoning_tokens"] for s in stages),
        "total_turns": sum(s["turns"] for s in stages),
        "total_tool_calls": sum(s["tool_calls"] for s in stages),
        "added_loc": added_loc,
        "own_tests_passed": own_ok,
        "stages": stages
    }
    json.dump(res, open(f"{WORK_R2}/{cid}_result.json", "w"), indent=2)
    log(f"[{cid}] COMPLETE: own_tests={own_ok} tot_tok={res['total_tokens']} wall={wall_s}s added_loc={added_loc}")
    return res

def run_group(cids):
    out = []
    for c in [p for p in PIPELINES if p["id"] in cids]:
        out.append(run_pipeline(c))
    return out

if __name__ == "__main__":
    # 5 balanced worker groups across distinct model families so no single model endpoint bottlenecks!
    groups = [
        ["R2_C1_solo_mistral_large_4", "R2_C7_hetero_qwen2_4t_ml4_k3"],
        ["R2_C2_solo_qwen3_8_2_4t", "R2_C9_hetero_ml4_ds41_qwen2_4t"],
        ["R2_C3_solo_qwen4_max", "R2_C6_homo_ml4_4stage"],
        ["R2_C4_solo_muse_spark_open", "R2_C8_hetero_k3_muse_ml4"],
        ["R2_C5_solo_deepseek_v4_pro", "R2_C10_hetero_dsv4pro_devstral_glm53"],
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(run_group, g) for g in groups]
        results = []
        for f in futs:
            results.extend(f.result())
    json.dump(results, open(f"{WORK_R2}/round2_pipelines_raw.json", "w"), indent=2)
    log("ALL_10_ROUND2_PIPELINES_COMPLETE")
