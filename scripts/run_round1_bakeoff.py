import os, sys, json, time, shutil, tempfile, subprocess, random, concurrent.futures

WORK_ST4 = "/tmp/subtasks/st4_bakeoff"
WORK_ST3 = "/tmp/subtasks/st3_gold"
NURI_REPO = "/Users/eminmahrt/Developer/nuri-server-musig2-v4-arkade"
ORIGIN_SHA = "136a54faa0c1af817cf9f829412582291a7ec83f"
MODELS_JSON = f"{WORK_ST4}/models.json"
LOG = open("/tmp/subtasks/logs/st4_bakeoff.log", "w", buffering=1)

V3_SKILL = """CAVEMAN + ADHD MODE. Active until "stop adhd mode".
Fewest words possible. No fixed word count. Max 3 bullets/steps. Answer first. Short fragments OK. No filler, recaps or tangents. Explain only when asked; obey requested format.
Code like caveman: reuse first. Minimum code, files, tools, dependencies, abstractions. No broad reads. Keep correctness, exact syntax, negations, tests and security.
Tool output: quiet flags; needed lines/failures only. Reuse commands; no repeated reads.
"""

def log(msg):
    LOG.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(msg, flush=True)

def run_pi(provider, model, prompt, cwd, tools=True, timeout=540):
    ag = tempfile.mkdtemp(prefix="pi-st4-")
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
            "--provider", provider, "--model", model, "--thinking", "max",
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

TASK_PROMPT = open(f"{WORK_ST3}/TASK_PROMPT.md").read()

PIPELINES = [
    {
        "id": "C1_solo_k3_max",
        "label": "Solo Single-Brain: k3.1-pro (1-shot agent)",
        "mode": "solo",
        "worker": "k3.1-pro"
    },
    {
        "id": "C2_homo_k3_4stage",
        "label": "Homogeneous 4-Stage: k3.1-pro -> k3.1-pro -> k3.1-pro -> k3.1-pro",
        "mode": "pipeline",
        "planner": "k3.1-pro",
        "worker": "k3.1-pro",
        "reviewer": "k3.1-pro",
        "orchestrator": "k3.1-pro"
    },
    {
        "id": "C3_hetero_k3_ds_glm",
        "label": "Hetero Speed-Brain: Planner k3.1-pro + Worker deepseek-v4.1-flash + Reviewer glm-5.3 + Orch deepseek-v4.1-flash",
        "mode": "pipeline",
        "planner": "k3.1-pro",
        "worker": "deepseek-v4.1-flash-abliterated",
        "reviewer": "glm-5.3-abliterated",
        "orchestrator": "deepseek-v4.1-flash-abliterated"
    },
    {
        "id": "C4_hetero_glm_kimi_k3",
        "label": "Hetero Coding-Specialist: Planner glm-5.3 + Worker kimi-for-coding + Reviewer k3.1-pro + Orch kimi-for-coding",
        "mode": "pipeline",
        "planner": "glm-5.3-abliterated",
        "worker": "kimi-for-coding",
        "reviewer": "k3.1-pro",
        "orchestrator": "kimi-for-coding"
    },
    {
        "id": "C5_hetero_nem_ds_k3",
        "label": "Hetero Diverse-Family: Planner nemotron-3-ultra-550b + Worker deepseek-v4.1-flash + Reviewer k3.1-pro + Orch deepseek-v4.1-flash",
        "mode": "pipeline",
        "planner": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "worker": "deepseek-v4.1-flash-abliterated",
        "reviewer": "k3.1-pro",
        "orchestrator": "deepseek-v4.1-flash-abliterated"
    },
    {
        "id": "C6_solo_deepseek_v4_1",
        "label": "Solo Fast-Brain Control: deepseek-v4.1-flash-abliterated (1-shot agent)",
        "mode": "solo",
        "worker": "deepseek-v4.1-flash-abliterated"
    }
]

def setup_wt(cid):
    wt = f"{WORK_ST4}/wt_{cid}"
    if os.path.exists(wt):
        subprocess.run(["git", "worktree", "remove", "--force", wt], cwd=NURI_REPO)
    subprocess.run(["git", "worktree", "add", "--detach", wt, ORIGIN_SHA], cwd=NURI_REPO, check=True)
    if not os.path.exists(f"{wt}/node_modules"):
        os.symlink("/tmp/subtasks/st2_audit/nuri-server-wt/node_modules", f"{wt}/node_modules")
    return wt

def run_pipeline(cfg):
    cid = cfg["id"]
    wt = setup_wt(cid)
    log(f"[{cid}] Starting ({cfg['label']})...")
    stages = []
    t_start = time.time()

    if cfg["mode"] == "solo":
        s_work = run_pi("paymentrequired", cfg["worker"], TASK_PROMPT, cwd=wt, tools=True, timeout=600)
        s_work["stage"] = "solo_worker"
        stages.append(s_work)
    else:
        # Stage 1: Planner (inspects codebase & produces crisp atomic blueprint)
        plan_prompt = f"""ROLE: Planner / Architect. Do NOT edit files. Inspect only exact relevant lines in `src/ArkadeServer.js`, `src/ArkadeConfig.js`, `src/ArkadeNotifications.js`, `ENDPOINTS.md`, and output a tight atomic implementation blueprint (<350 words) for the Worker covering file edits, exact line numbers/helpers to reuse (`verifyRequestAuth`, `getClientSignerFromToken`, `getDerivedServerPublicKey`, `deriveAggregatedPk33`), JCS SHA-256 IDs, BIP-68 CSV encoding traps, and security checks.

TASK:
{TASK_PROMPT}"""
        s_plan = run_pi("paymentrequired", cfg["planner"], plan_prompt, cwd=wt, tools=True, timeout=360)
        s_plan["stage"] = "planner"
        stages.append(s_plan)
        log(f"[{cid}] Planner ({cfg['planner']}) done: {s_plan['total_tokens']} tok, {s_plan['elapsed_s']}s")

        # Stage 2: Worker (implements code + tests following blueprint + task spec)
        work_prompt = f"""ROLE: Worker. Implement the task completely and run `node --test src/ArkadeExecutorClient.test.js` until green.

PLANNER BLUEPRINT:
{s_plan['text']}

EXACT TASK SPECIFICATION:
{TASK_PROMPT}"""
        s_work = run_pi("paymentrequired", cfg["worker"], work_prompt, cwd=wt, tools=True, timeout=540)
        s_work["stage"] = "worker"
        stages.append(s_work)
        log(f"[{cid}] Worker ({cfg['worker']}) done: {s_work['total_tokens']} tok, {s_work['elapsed_s']}s")

        # Stage 3: Reviewer (different brain or same brain reviews git diff + test run!)
        subprocess.run(["git", "add", "-N", "."], cwd=wt)
        cand_diff = subprocess.run(["git", "diff"], cwd=wt, capture_output=True, text=True).stdout
        test_mid = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt, capture_output=True, text=True, timeout=60)
        rev_prompt = f"""ROLE: Adversarial Security & Protocol Reviewer. Do NOT edit files. Inspect the candidate diff and test output against the specification. List ONLY real bugs, security bypasses (ownership/IDOR, purpose-scoped token, admin port leak, secret leak), encoding errors (`encodeScriptNumHex`, BIP-68 seconds % 512, JCS SHA-256), or missing deliverables. If zero issues, reply `APPROVED_NO_FIXES`.

TASK SPEC:
{TASK_PROMPT}

TEST OUTPUT (rc={test_mid.returncode}):
{(test_mid.stdout + test_mid.stderr)[-2000:]}

GIT DIFF:
```diff
{cand_diff[:35000]}
```"""
        s_rev = run_pi("paymentrequired", cfg["reviewer"], rev_prompt, cwd=wt, tools=False, timeout=300)
        s_rev["stage"] = "reviewer"
        stages.append(s_rev)
        log(f"[{cid}] Reviewer ({cfg['reviewer']}) done: {s_rev['total_tokens']} tok, {s_rev['elapsed_s']}s | verdict={s_rev['text'][:80].replace(chr(10),' ')}")

        # Stage 4: Orchestrator / Finisher (applies Reviewer fixes if needed & ensures tests pass)
        if "APPROVED_NO_FIXES" not in s_rev["text"] or test_mid.returncode != 0:
            orch_prompt = f"""ROLE: Orchestrator / Finisher. Verify each Reviewer finding below; apply real fixes with minimal code changes and ensure `node --test src/ArkadeExecutorClient.test.js` exits 0.

REVIEWER FINDINGS:
{s_rev['text']}"""
            s_orch = run_pi("paymentrequired", cfg["orchestrator"], orch_prompt, cwd=wt, tools=True, timeout=360)
            s_orch["stage"] = "orchestrator_fix"
            stages.append(s_orch)
            log(f"[{cid}] Orchestrator ({cfg['orchestrator']}) done: {s_orch['total_tokens']} tok, {s_orch['elapsed_s']}s")

    wall_s = round(time.time() - t_start, 2)
    subprocess.run(["git", "add", "-N", "."], cwd=wt)
    final_diff = subprocess.run(["git", "diff"], cwd=wt, capture_output=True, text=True).stdout
    open(f"{WORK_ST4}/{cid}.patch", "w").write(final_diff)

    # Own unit test pass check
    own_t = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt, capture_output=True, text=True, timeout=60)
    added_loc = sum(1 for l in final_diff.splitlines() if l.startswith("+") and not l.startswith("+++") and l[1:].strip())

    res = {
        "id": cid,
        "label": cfg["label"],
        "mode": cfg["mode"],
        "wall_s": wall_s,
        "total_tokens": sum(s["total_tokens"] for s in stages),
        "output_tokens": sum(s["output_tokens"] for s in stages),
        "reasoning_tokens": sum(s["reasoning_tokens"] for s in stages),
        "total_turns": sum(s["turns"] for s in stages),
        "total_tool_calls": sum(s["tool_calls"] for s in stages),
        "added_loc": added_loc,
        "own_tests_passed": own_t.returncode == 0,
        "stages": stages
    }
    json.dump(res, open(f"{WORK_ST4}/{cid}_result.json", "w"), indent=2)
    log(f"[{cid}] COMPLETE: own_tests={res['own_tests_passed']} tot_tok={res['total_tokens']} wall={wall_s}s added_loc={added_loc}")
    return res

# Run fast pipelines in parallel (max 2 concurrent Kimi calls so router never queues!)
# Group A (uses k3.1-pro heavily): C1, C2 -> run sequentially in thread A
# Group B (uses fast models + 1 k3 stage): C3, C6 -> run in thread B
# Group C: C4, C5 -> run in thread C
def run_group(cids):
    out = []
    for c in [p for p in PIPELINES if p["id"] in cids]:
        out.append(run_pipeline(c))
    return out

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    f1 = ex.submit(run_group, ["C1_solo_k3_max", "C2_homo_k3_4stage"])
    f2 = ex.submit(run_group, ["C3_hetero_k3_ds_glm", "C6_solo_deepseek_v4_1"])
    f3 = ex.submit(run_group, ["C4_hetero_glm_kimi_k3", "C5_hetero_nem_ds_k3"])
    results = f1.result() + f2.result() + f3.result()

json.dump(results, open(f"{WORK_ST4}/all_pipelines_raw.json", "w"), indent=2)
log("ALL_6_OPEN_MODEL_PIPELINES_COMPLETE")
