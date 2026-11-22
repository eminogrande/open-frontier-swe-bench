import os, sys, json, time, glob, shutil, tempfile, subprocess, concurrent.futures

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

WORK_R4 = "/private/tmp/bench_clean/r4_hermetic"
CLEAN_ROOT = "/private/tmp/bench_clean"
BASE_REPO = f"{CLEAN_ROOT}/base_repo"
BASE_NODE_MODULES = f"{CLEAN_ROOT}/base_node_modules"
UPSTREAM_DIR = f"{CLEAN_ROOT}/upstream"

WORK_ST3 = "/private/tmp/subtasks/st3_gold"
WORK_ST4 = "/private/tmp/subtasks/st4_bakeoff"

os.makedirs(WORK_R4, exist_ok=True)
os.makedirs(f"{CLEAN_ROOT}/logs", exist_ok=True)
LOG = open(f"{CLEAN_ROOT}/logs/r4_hermetic.log", "a", buffering=1)

V3_SKILL = open("/Users/eminmahrt/Developer/agent-prompt-brevity-bench/prompts/V3_caveman_adhd_winner.md").read()
TASK_PROMPT = open(f"{WORK_ST3}/TASK_PROMPT.md").read()

st4_provs = json.load(open(f"{WORK_ST4}/models.json"))["providers"]
NOUS_KEY = st4_provs["nous"]["apiKey"]
PR_KEY = st4_provs["paymentrequired"]["apiKey"]

SANDBOX_PROFILE = f"{CLEAN_ROOT}/hermetic_agent.sb"
with open(SANDBOX_PROFILE, "w") as _sbf:
    _sbf.write("""(version 1)
(allow default)
(deny file-read* file-write*
  (subpath "/private/tmp/subtasks")
  (subpath "/Users/eminmahrt/Developer/open-frontier-swe-bench")
  (subpath "/Users/eminmahrt/Developer/nuri-server-musig2-v4-arkade")
  (subpath "/Users/eminmahrt/Developer/.worktrees")
  (subpath "/Users/eminmahrt/Developer/_arkade_v4")
  (subpath "/Users/eminmahrt/.dsh/sessions")
  (subpath "/Users/eminmahrt/.dsh/skills")
  (subpath "/Users/eminmahrt/.kimi-code/sessions")
  (subpath "/Users/eminmahrt/.kimi-code/file-history")
  (subpath "/Users/eminmahrt/.agents/skills")
)
""")

def make_sandbox_profile(current_wt):
    """Block all reference dirs AND sibling candidate worktrees so parallel runs cannot peek at each other."""
    other_wts = [
        os.path.realpath(p)
        for p in glob.glob(f"{WORK_R4}/wt_*")
        if os.path.realpath(p) != os.path.realpath(current_wt)
    ]
    extra = "\n".join(f'  (subpath "{p}")' for p in other_wts)
    sf = tempfile.NamedTemporaryFile("w", suffix=".sb", delete=False)
    sf.write(f"""(version 1)
(allow default)
(deny file-read* file-write*
  (subpath "/private/tmp/subtasks")
  (subpath "/Users/eminmahrt/Developer/open-frontier-swe-bench")
  (subpath "/Users/eminmahrt/Developer/nuri-server-musig2-v4-arkade")
  (subpath "/Users/eminmahrt/Developer/.worktrees")
  (subpath "/Users/eminmahrt/Developer/_arkade_v4")
  (subpath "/Users/eminmahrt/.dsh/sessions")
  (subpath "/Users/eminmahrt/.dsh/skills")
  (subpath "/Users/eminmahrt/.kimi-code/sessions")
  (subpath "/Users/eminmahrt/.kimi-code/file-history")
  (subpath "/Users/eminmahrt/.agents/skills")
{extra}
)
""")
    sf.close()
    return sf.name

def log(msg):
    LOG.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(msg, flush=True)

def run_cmd_sandboxed(cmd, cwd, env, timeout, sandbox=True):
    t0 = time.time()
    sb_file = make_sandbox_profile(cwd) if sandbox else None
    full_cmd = (["sandbox-exec", "-f", sb_file] + cmd) if sb_file else cmd
    proc = subprocess.Popen(
        full_cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True
    )
    try:
        out_s, err_s = proc.communicate(timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, 15)
            time.sleep(1.5)
            os.killpg(proc.pid, 9)
        except Exception:
            pass
        out_s, err_s = proc.communicate()
        rc = -1
        err_s = (err_s or "") + f"\nTIMEOUT after {timeout}s"
    finally:
        if sb_file and os.path.exists(sb_file):
            os.unlink(sb_file)
    return rc, out_s or "", (err_s or "")[-500:], round(time.time() - t0, 2)

NOUS_MODELS = [
    "moonshotai/kimi-k3.1-pro",
    "mistralai/mistral-large-4-0",
    "qwen/qwen3.8-2.4t-a95b",
    "deepseek/deepseek-v4.1-flash-1017",
    "minimax/minimax-m3.1-flash",
    "tencent/hy4",
    "anthropic/claude-fable-5.2",
]

def run_pi(provider, model, prompt, cwd, tools=True, timeout=540):
    ag = tempfile.mkdtemp(prefix="r4-pi-")
    try:
        models_doc = {
            "providers": {
                "nous": {
                    "baseUrl": "https://inference-api.nousresearch.com/v1",
                    "apiKey": NOUS_KEY,
                    "api": "openai-completions",
                    "models": [
                        {"id": m, "name": m, "reasoning": True, "input": ["text"], "contextWindow": 262144, "maxTokens": 32768}
                        for m in NOUS_MODELS
                    ]
                },
                "pr": {
                    "baseUrl": "https://router.paymentrequired.com/v1/internal",
                    "apiKey": PR_KEY,
                    "api": "openai-completions",
                    "models": [
                        {"id": "deepseek-v4.1-flash-abliterated", "name": "ds-v4.1-flash", "reasoning": True, "input": ["text"], "contextWindow": 262144, "maxTokens": 32768},
                    ]
                }
            }
        }
        json.dump(models_doc, open(f"{ag}/models.json", "w"))
        open(f"{ag}/settings.json", "w").write("{}")
        open(f"{ag}/trust.json", "w").write("{}")
        open(f"{ag}/APPEND_SYSTEM.md", "w").write(V3_SKILL)
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = ag
        cmd = [
            "/Users/eminmahrt/.local/bin/pi", "-p", "--mode", "json", "--no-session", "--no-context-files",
            "--no-extensions", "--no-mcp", "--no-skills",
            *([] if tools else ["--no-tools"]),
            "--provider", provider, "--model", model, "--thinking", "max",
            "--", prompt
        ]
        rc, out_s, err_s, elapsed = run_cmd_sandboxed(cmd, cwd, env, timeout, sandbox=True)
        tot_tok = in_tok = out_tok = rsn_tok = turns = tool_calls = 0
        final_txt = ""
        for line in out_s.splitlines():
            if not line.strip().startswith("{"): continue
            try: ev = json.loads(line)
            except Exception: continue
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
                if txts: final_txt = "\n".join(txts)
        return {
            "harness": "pi-1.5.2", "model": f"{provider}/{model}", "rc": rc, "elapsed_s": elapsed,
            "turns": turns, "tool_calls": tool_calls,
            "total_tokens": tot_tok, "input_tokens": in_tok, "output_tokens": out_tok, "reasoning_tokens": rsn_tok,
            "text": final_txt, "stderr": err_s
        }
    finally:
        shutil.rmtree(ag, ignore_errors=True)

def run_dsh(provider, model, prompt, cwd, tools=True, timeout=540):
    dsh_home = tempfile.mkdtemp(prefix="r4-dsh-home-")
    os.symlink(os.path.expanduser("~/.dsh/profiles"), f"{dsh_home}/profiles")
    os.makedirs(f"{dsh_home}/sessions", exist_ok=True)
    os.makedirs(f"{dsh_home}/skills", exist_ok=True)
    patch_f = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False)
    v3_indented = V3_SKILL.replace("\n", "\n      ")
    disable_tools_block = "" if tools else "\n".join(
        f"- id: {t}\n  disabled: true"
        for t in ["tool-bash", "tool-pwsh", "tool-jobs", "tool-fs", "tool-fs-search", "tool-subagent", "tool-subagent-fork", "tool-workflow", "tool-web"]
    )
    nous_yaml = "\n".join(f"          - id: {m}\n            contextWindow: 1048576" for m in NOUS_MODELS)
    patch_f.write(f"""
- id: agent-default-model
  config:
    provider: {provider}
    model: {model}
- id: system-prompt
  config:
    personaPrefix: |
      You are a coding agent powered by the {{{{model}}}} model.
      {v3_indented}
- id: llm-pi-ai
  config:
    providers:
      402router:
        displayName: paymentrequired.com
        apiKeyEnv: ROUTER_INTERNAL_KEY
        api: openai-completions
        baseURL: https://router.paymentrequired.com/v1/internal
        compat:
          supportsDeveloperRole: false
          maxTokensField: max_tokens
        models:
          - id: deepseek-v4.1-flash-abliterated
            contextWindow: 1048576
      nous:
        displayName: Nous
        apiKeyEnv: NOUS_API_KEY
        api: openai-completions
        baseURL: https://inference-api.nousresearch.com/v1
        compat:
          supportsDeveloperRole: false
          maxTokensField: max_tokens
        models:
{nous_yaml}
{disable_tools_block}
""")
    patch_f.close()
    try:
        env = os.environ.copy()
        env["DSH_HOME"] = dsh_home
        env["ROUTER_INTERNAL_KEY"] = PR_KEY
        env["NOUS_API_KEY"] = NOUS_KEY
        env["DSH_PERMISSION_MODE"] = "danger-full-access"
        cmd = ["/Users/eminmahrt/.volta/bin/dsh", "--profile", "headless", "--patch", patch_f.name, "--json", prompt]
        rc, out_s, err_s, elapsed = run_cmd_sandboxed(cmd, cwd, env, timeout, sandbox=True)
        tot_tok = in_tok = out_tok = rsn_tok = steps = tool_calls = 0
        final_txt = last_text = ""
        for line in out_s.splitlines():
            if not line.strip().startswith("{"): continue
            try: ev = json.loads(line)
            except Exception: continue
            tp = ev.get("type")
            if tp == "tool_call":
                tool_calls += 1
            elif tp == "text":
                last_text = ev.get("text", "")
            elif tp == "final" and ev.get("text"):
                final_txt = ev.get("text", "")
            elif tp == "status" and ev.get("phase") == "step_end":
                steps += 1
                u = ev.get("usage") or {}
                it, cr, ot = u.get("inputTokens", 0), u.get("cacheReadTokens", 0), u.get("outputTokens", 0)
                in_tok += (it + cr)
                out_tok += ot
                tot_tok += (u.get("totalTokens") or (it + cr + ot))
        return {
            "harness": "dsh-0.2.1-rc.5", "model": f"{provider}/{model}", "rc": rc, "elapsed_s": elapsed,
            "turns": steps, "tool_calls": tool_calls,
            "total_tokens": tot_tok, "input_tokens": in_tok, "output_tokens": out_tok, "reasoning_tokens": rsn_tok,
            "text": final_txt or last_text, "stderr": err_s
        }
    finally:
        if os.path.exists(patch_f.name):
            os.unlink(patch_f.name)
        shutil.rmtree(dsh_home, ignore_errors=True)

def run_kimi_cli(model_alias, prompt, cwd, timeout=540, system_prompt=V3_SKILL, thinking_effort=None):
    kimi_home = tempfile.mkdtemp(prefix="r4-kimi-home-")
    empty_skills = tempfile.mkdtemp(prefix="r4-kimi-skills-")
    for item in ["config.toml", "credentials", "oauth", "device_id", "region"]:
        src = os.path.expanduser(f"~/.kimi-code/{item}")
        if os.path.exists(src):
            shutil.copytree(src, f"{kimi_home}/{item}", symlinks=True) if os.path.isdir(src) else shutil.copy2(src, f"{kimi_home}/{item}")
    try:
        env = os.environ.copy()
        env["KIMI_CODE_HOME"] = kimi_home
        if thinking_effort:
            env["KIMI_MODEL_THINKING_EFFORT"] = thinking_effort
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt.strip() else prompt
        cmd = [
            "/Users/eminmahrt/.kimi-code/bin/kimi",
            "--skills-dir", empty_skills,
            "--model", model_alias,
            "--output-format", "stream-json",
            "-p", full_prompt
        ]
        rc, out_s, err_s, elapsed = run_cmd_sandboxed(cmd, cwd, env, timeout, sandbox=True)
        tot_tok = in_tok = out_tok = rsn_tok = steps = tool_calls = 0
        final_txt = session_id = ""
        for line in out_s.splitlines():
            if not line.strip().startswith("{"): continue
            try: ev = json.loads(line)
            except Exception: continue
            if ev.get("role") == "assistant":
                tool_calls += len(ev.get("tool_calls") or [])
                if ev.get("content"):
                    final_txt = ev.get("content", "")
            elif ev.get("type") == "session.resume_hint":
                session_id = ev.get("session_id", "")
        if session_id:
            for wf in glob.glob(f"{kimi_home}/sessions/**/{session_id}/agents/*/wire.jsonl", recursive=True):
                for wl in open(wf, errors="ignore"):
                    if '"usage.record"' in wl:
                        try:
                            wev = json.loads(wl)
                            if wev.get("type") == "usage.record":
                                steps += 1
                                u = wev.get("usage") or {}
                                io = u.get("inputOther", 0) + u.get("inputCacheRead", 0) + u.get("inputCacheCreation", 0)
                                ot = u.get("output", 0)
                                in_tok += io
                                out_tok += ot
                                tot_tok += (io + ot)
                        except Exception:
                            pass
        return {
            "harness": "kimi-code-2.5.2", "model": model_alias, "rc": rc, "elapsed_s": elapsed,
            "turns": steps, "tool_calls": tool_calls,
            "total_tokens": tot_tok, "input_tokens": in_tok, "output_tokens": out_tok, "reasoning_tokens": rsn_tok,
            "text": final_txt, "stderr": err_s
        }
    finally:
        shutil.rmtree(empty_skills, ignore_errors=True)
        shutil.rmtree(kimi_home, ignore_errors=True)

def dispatch(spec, prompt, cwd, tools=True, timeout=540):
    h = spec["harness"]
    if h == "pi":
        return run_pi(spec["provider"], spec["model"], prompt, cwd, tools=tools, timeout=timeout)
    if h == "dsh":
        return run_dsh(spec["provider"], spec["model"], prompt, cwd, tools=tools, timeout=timeout)
    if h == "kimi":
        return run_kimi_cli(spec["model"], prompt, cwd, timeout=timeout)
    raise ValueError(f"Unknown harness: {h}")

# 8 Round 4 Open-Frontier Beat-Gold Pipelines (100% open weights, hermetically sandboxed!)
KIMI_PLAN = {"harness": "kimi", "model": "kimi-code/k3.1-pro-highspeed"}
DSH_DS41 = {"harness": "dsh", "provider": "nous",      "model": "deepseek/deepseek-v4.1-flash-1017"}
PI_DS41  = {"harness": "pi",  "provider": "nous",      "model": "deepseek/deepseek-v4.1-flash-1017"}
REV_KIMI = {"harness": "pi",  "provider": "nous",      "model": "moonshotai/kimi-k3.1-pro"}
REV_ML4  = {"harness": "pi",  "provider": "nous",      "model": "mistralai/mistral-large-4-0"}
PI_MM31  = {"harness": "pi",  "provider": "nous",      "model": "minimax/minimax-m3.1-flash"}
KIMI_W   = {"harness": "kimi","model": "kimi-code/k3.1-pro-highspeed"}

PIPELINES = [
    {
        "id": "R4_P1_dream_kimi_rev",
        "label": "R3 #1 Fixed Reviewer: kimi-cli(k3.1-hs) -> dsh(ds-v4.1) -> pi(k3.1-pro) -> dsh(ds-v4.1)",
        "mode": "pipeline",
        "planner": KIMI_PLAN, "worker": DSH_DS41, "reviewers": [REV_KIMI], "orchestrator": DSH_DS41
    },
    {
        "id": "R4_P2_dream_ml4_rev",
        "label": "R3 #1 Fixed ML4 Reviewer: kimi-cli(k3.1-hs) -> dsh(ds-v4.1) -> pi(ml4) -> dsh(ds-v4.1)",
        "mode": "pipeline",
        "planner": KIMI_PLAN, "worker": DSH_DS41, "reviewers": [REV_ML4], "orchestrator": DSH_DS41
    },
    {
        "id": "R4_P3_dream_dual_rev",
        "label": "Dual-Brain Review Panel: kimi-cli(k3.1-hs) -> dsh(ds-v4.1) -> [pi(k3.1) || pi(ml4)] -> dsh(ds-v4.1)",
        "mode": "pipeline",
        "planner": KIMI_PLAN, "worker": DSH_DS41, "reviewers": [REV_KIMI, REV_ML4], "orchestrator": DSH_DS41
    },
    {
        "id": "R4_P4_parallel_dsh_gold_parity",
        "label": "Gold-Parity Parallel DSH: kimi-cli(k3.1-hs) -> [2x dsh || -> dsh] -> [pi(k3.1) || pi(ml4)] -> dsh",
        "mode": "parallel_gold",
        "planner": KIMI_PLAN, "worker": DSH_DS41, "reviewers": [REV_KIMI, REV_ML4], "orchestrator": DSH_DS41
    },
    {
        "id": "R4_P5_parallel_pi_lean",
        "label": "Gold-Parity Parallel Lean Pi: kimi-cli(k3.1-hs) -> [2x pi || -> pi] -> [pi(k3.1) || pi(ml4)] -> pi",
        "mode": "parallel_gold",
        "planner": KIMI_PLAN, "worker": PI_DS41, "reviewers": [REV_KIMI, REV_ML4], "orchestrator": PI_DS41
    },
    {
        "id": "R4_P6_lean_pi_dual_rev",
        "label": "Lean Pi 4-Stage Dual-Rev: kimi-cli(k3.1-hs) -> pi(ds-v4.1) -> [pi(k3.1) || pi(ml4)] -> pi(ds-v4.1)",
        "mode": "pipeline",
        "planner": KIMI_PLAN, "worker": PI_DS41, "reviewers": [REV_KIMI, REV_ML4], "orchestrator": PI_DS41
    },
    {
        "id": "R4_P7_minimax_m31_worker",
        "label": "New Contender MiniMax-M3.1-Flash: kimi-cli(k3.1-hs) -> pi(minimax-m3.1-flash) -> pi(k3.1) -> pi(minimax-m3.1-flash)",
        "mode": "pipeline",
        "planner": KIMI_PLAN, "worker": PI_MM31, "reviewers": [REV_KIMI], "orchestrator": PI_MM31
    },
    {
        "id": "R4_P8_parallel_hetero_kimi_ds",
        "label": "Hetero Parallel Specialists: kimi-cli(k3.1-hs) -> [kimi(cov) || pi(client) -> dsh(server)] -> [pi(k3.1) || pi(ml4)] -> dsh",
        "mode": "parallel_hetero",
        "planner": KIMI_PLAN, "worker_cov": KIMI_W, "worker_cli": PI_DS41, "worker_srv": DSH_DS41,
        "reviewers": [REV_KIMI, REV_ML4], "orchestrator": DSH_DS41
    },
]

def setup_wt(cid):
    """Create a fresh standalone git clone (ZERO shared .git/worktrees metadata!) + clean node_modules symlink."""
    wt = f"{WORK_R4}/wt_{cid}"
    if os.path.exists(wt):
        shutil.rmtree(wt)
    subprocess.run(["git", "clone", "-q", BASE_REPO, wt], check=True)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=wt, check=True)
    os.symlink(BASE_NODE_MODULES, f"{wt}/node_modules")
    return wt

def clean_wt_diff(wt):
    subprocess.run(["git", "add", "-N", "."], cwd=wt)
    subprocess.run(["git", "reset", "-q", "--", "node_modules"], cwd=wt)
    return subprocess.run(["git", "diff", "--", ":!node_modules"], cwd=wt, capture_output=True, text=True).stdout

def run_review_panel(reviewers, diff_txt, test_mid, cwd):
    rev_prompt = f"""ROLE: Adversarial Principal Security & Protocol Reviewer. You have NO file tools; the COMPLETE candidate git diff and test output are inline below—analyze EVERY file directly right now!
Audit strictly for:
1. Protocol & encoding correctness: exact schema/hash invariants, edge-case integer/numeric width & bounds, negative/zero validation, and spec fidelity.
2. Security & boundary hardening: auth/ownership binding, cross-user IDOR across all routes, statelessness/restart resilience, admin/redirect/response-size/error-handling boundaries, and zero credential/URL leaks.
3. Craft, tests & docs: minimal clean diffs reusing existing helpers, avoiding duplicated logic or unnecessary state, zero regressions, realistic live-HTTP tests, and concise docs.

List ONLY genuine defects with exact file/function names and minimal fixes. If zero defects exist, reply `APPROVED_NO_FIXES`.

TASK SPEC:
{TASK_PROMPT}

TEST OUTPUT (rc={test_mid.returncode}):
{(test_mid.stdout + test_mid.stderr)[-2500:]}

COMPLETE GIT DIFF:
```diff
{diff_txt[:100000]}
```"""
    if len(reviewers) == 1:
        r = dispatch(reviewers[0], rev_prompt, cwd=cwd, tools=False, timeout=300)
        r["stage"] = "reviewer"
        return [r]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(reviewers)) as ex:
        futs = [ex.submit(dispatch, rv, rev_prompt, cwd, False, 300) for rv in reviewers]
        out = []
        for idx, f in enumerate(futs):
            r = f.result()
            r["stage"] = f"reviewer_{idx+1}"
            out.append(r)
        return out

def run_pipeline(cfg):
    cid = cfg["id"]
    wt = setup_wt(cid)
    log(f"[{cid}] Starting hermetic run ({cfg['label']})...")
    stages = []
    t_start = time.time()

    is_parallel = cfg["mode"] in ("parallel_gold", "parallel_hetero")
    plan_extra = (
        "\nDivide execution into 3 strictly disjoint file slices with exact exported symbol names/signatures so Wave-1 workers run in parallel without conflicts:\n"
        "- Slice A: `scripts/fixtures/nuri_delegated_vtxo.json`, `scripts/fixtures/nuri_renew.json`\n"
        "- Slice B: `src/ArkadeConfig.js`, `src/ArkadeExecutorClient.js`\n"
        "- Slice C: `src/ArkadeServer.js`, `ENDPOINTS.md`, `src/ArkadeExecutorClient.test.js`\n"
        if is_parallel else ""
    )
    plan_prompt = f"""ROLE: Planner / Architect. Do NOT edit files. Inspect exact relevant lines in `src/ArkadeServer.js`, `src/ArkadeConfig.js`, `src/ArkadeNotifications.js`, `ENDPOINTS.md`, and the upstream reference repos in `{UPSTREAM_DIR}/delegatee` and `{UPSTREAM_DIR}/emulator`. Output a crisp atomic implementation blueprint (<400 words) covering exact file edits, existing helpers to reuse (`verifyRequestAuth`, `getClientSignerFromToken`, `getDerivedServerPublicKey`, `deriveAggregatedPk33`), exact schema/encoding invariants, and security boundaries.
VERBATIM SPEC RULE: Copy ALL exact exported function/symbol names, JSON field keys, HTTP route paths, env var names, error codes, and file paths VERBATIM from the TASK — never paraphrase or rename public identifiers.{plan_extra}

TASK:
{TASK_PROMPT}"""
    s_plan = dispatch(cfg["planner"], plan_prompt, cwd=wt, tools=True, timeout=360)
    s_plan["stage"] = "planner"
    stages.append(s_plan)
    log(f"[{cid}] Planner done: {s_plan['total_tokens']} tok, {s_plan['elapsed_s']}s")

    if not is_parallel:
        work_prompt = f"""ROLE: Worker. Implement the task completely with minimal clean code (upstream OSS repos `{UPSTREAM_DIR}/delegatee` and `{UPSTREAM_DIR}/emulator` are available read-only if needed) and run `node --test src/ArkadeExecutorClient.test.js` until green.

PLANNER BLUEPRINT:
{s_plan['text']}

EXACT TASK SPECIFICATION:
{TASK_PROMPT}"""
        s_work = dispatch(cfg["worker"], work_prompt, cwd=wt, tools=True, timeout=540)
        s_work["stage"] = "worker"
        stages.append(s_work)
        log(f"[{cid}] Worker done: {s_work['total_tokens']} tok, {s_work['elapsed_s']}s")
    else:
        w_cov_spec = cfg.get("worker_cov") or cfg["worker"]
        w_cli_spec = cfg.get("worker_cli") or cfg["worker"]
        w_srv_spec = cfg.get("worker_srv") or cfg["worker"]

        p_cov = f"""ROLE: Parallel Worker A (Fixtures ONLY). Create ONLY `scripts/fixtures/nuri_delegated_vtxo.json` and `scripts/fixtures/nuri_renew.json` (do NOT duplicate fixtures anywhere else or touch `src/`!). Upstream OSS `{UPSTREAM_DIR}/delegatee` and `{UPSTREAM_DIR}/emulator` are available read-only. Verify RFC-8785 JCS SHA-256 artifact ID match with `node -e`.

PLANNER BLUEPRINT:
{s_plan['text']}

EXACT TASK SPECIFICATION:
{TASK_PROMPT}"""
        p_cli = f"""ROLE: Parallel Worker B (Config & Executor Client ONLY). Edit/create ONLY `src/ArkadeConfig.js` and `src/ArkadeExecutorClient.js`. Do NOT touch `scripts/fixtures/`, `src/ArkadeServer.js`, or `ENDPOINTS.md`! Enforce all config, HTTP boundary, and uncertain-outcome invariants per spec.

PLANNER BLUEPRINT:
{s_plan['text']}

EXACT TASK SPECIFICATION:
{TASK_PROMPT}"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_cov = ex.submit(dispatch, w_cov_spec, p_cov, wt, True, 420)
            f_cli = ex.submit(dispatch, w_cli_spec, p_cli, wt, True, 420)
            s_cov, s_cli = f_cov.result(), f_cli.result()
        s_cov["stage"] = "worker_wave1_covenant"
        s_cli["stage"] = "worker_wave1_client"
        stages.extend([s_cov, s_cli])
        log(f"[{cid}] Wave-1 parallel done: cov={s_cov['elapsed_s']}s({s_cov['total_tokens']}t) cli={s_cli['elapsed_s']}s({s_cli['total_tokens']}t)")

        p_srv = f"""ROLE: Wave-2 Integration Worker C (Server Routes, Tests & Docs). Wave-1 workers ALREADY wrote `scripts/fixtures/*`, `src/ArkadeConfig.js`, and `src/ArkadeExecutorClient.js`. Inspect their exact exports first, then wire `src/ArkadeServer.js`, update `ENDPOINTS.md`, and write comprehensive unit + live-HTTP auth/IDOR/spoofing tests in `src/ArkadeExecutorClient.test.js`. Fix any integration mismatch if needed and run `node --test src/ArkadeExecutorClient.test.js` AND `node scripts/notifications-bind-proof.mjs` until both pass!

PLANNER BLUEPRINT:
{s_plan['text']}

EXACT TASK SPECIFICATION:
{TASK_PROMPT}"""
        s_srv = dispatch(w_srv_spec, p_srv, cwd=wt, tools=True, timeout=480)
        s_srv["stage"] = "worker_wave2_integration"
        stages.append(s_srv)
        log(f"[{cid}] Wave-2 integration done: {s_srv['elapsed_s']}s({s_srv['total_tokens']}t)")

    def run_hard_gate(wt_dir):
        test_file = f"{wt_dir}/src/ArkadeExecutorClient.test.js"
        if not os.path.exists(test_file):
            return False, "HARD TEST GATE FAILED: missing required test file `src/ArkadeExecutorClient.test.js`."
        t1 = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt_dir, capture_output=True, text=True, timeout=60)
        t2 = subprocess.run(["node", "scripts/notifications-bind-proof.mjs"], cwd=wt_dir, capture_output=True, text=True, timeout=60)
        if t1.returncode == 0 and t2.returncode == 0:
            return True, (t1.stdout + t1.stderr)[-2500:]
        err = f"ArkadeExecutorClient.test.js rc={t1.returncode}:\n{(t1.stdout+t1.stderr)[-1200:]}\nnotifications-bind-proof.mjs rc={t2.returncode}:\n{(t2.stdout+t2.stderr)[-800:]}"
        return False, err

    gate_ok, gate_out = run_hard_gate(wt)
    heal_spec = cfg.get("worker_srv") or cfg["worker"]
    for retry_i in range(2):
        if gate_ok:
            break
        log(f"[{cid}] onYield Hard Gate FAIL (retry {retry_i+1}/2) — auto-continuing worker...")
        s_heal = dispatch(heal_spec, f"HARD TEST GATE FAILED — fix every failure below and re-run both tests until exit 0:\n{gate_out}", cwd=wt, tools=True, timeout=300)
        s_heal["stage"] = f"onyield_retry_{retry_i+1}"
        stages.append(s_heal)
        gate_ok, gate_out = run_hard_gate(wt)

    cand_diff = clean_wt_diff(wt)
    test_mid = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt, capture_output=True, text=True, timeout=60)
    rev_stages = run_review_panel(cfg["reviewers"], cand_diff, test_mid, cwd=wt)
    stages.extend(rev_stages)

    valid_revs = [r for r in rev_stages if r["rc"] == 0 and r["text"].strip()]
    all_approved = bool(valid_revs) and all("APPROVED_NO_FIXES" in r["text"] for r in valid_revs)
    for r in rev_stages:
        log(f"[{cid}] {r['stage']} ({r['model']}) rc={r['rc']} {r['total_tokens']}t {r['elapsed_s']}s | {r['text'][:70].replace(chr(10),' ')}")

    if (not all_approved and valid_revs) or test_mid.returncode != 0:
        merged_findings = "\n\n---\n\n".join(
            f"### {r['stage']} ({r['model']})\n{r['text']}" for r in valid_revs
        ) or f"Tests failed (rc={test_mid.returncode}):\n{(test_mid.stdout + test_mid.stderr)[-1500:]}"
        orch_prompt = f"""ROLE: Surgical Finisher / Orchestrator. Verify each Reviewer finding below against the actual code; fix every genuine defect cleanly with minimal diff (avoid bloat, unneeded in-process state, or duplicated validation). Run BOTH `node --test src/ArkadeExecutorClient.test.js` AND `node scripts/notifications-bind-proof.mjs` until both exit 0!

REVIEWER FINDINGS:
{merged_findings}"""
        s_orch = dispatch(cfg["orchestrator"], orch_prompt, cwd=wt, tools=True, timeout=360)
        s_orch["stage"] = "orchestrator_fix"
        stages.append(s_orch)
        log(f"[{cid}] Finisher done: {s_orch['total_tokens']} tok, {s_orch['elapsed_s']}s")

    wall_s = round(time.time() - t_start, 2)
    final_diff = clean_wt_diff(wt)
    open(f"{WORK_R4}/{cid}.patch", "w").write(final_diff)

    test_f = f"{wt}/src/ArkadeExecutorClient.test.js"
    own_ok = (subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt, capture_output=True, text=True, timeout=60).returncode == 0) if os.path.exists(test_f) else False
    added_loc = sum(1 for l in final_diff.splitlines() if l.startswith("+") and not l.startswith("+++") and l[1:].strip())

    res = {
        "id": cid, "label": cfg["label"], "open_weights": True, "hermetic_sandbox": True, "mode": cfg["mode"],
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
    json.dump(res, open(f"{WORK_R4}/{cid}_result.json", "w"), indent=2)
    log(f"[{cid}] COMPLETE: own_tests={own_ok} tot_tok={res['total_tokens']} wall={wall_s}s added_loc={added_loc}")
    return res

def run_group(cids):
    return [run_pipeline(c) for c in PIPELINES if c["id"] in cids]

if __name__ == "__main__":
    only = set(sys.argv[1:])
    if only:
        to_run = [c["id"] for c in PIPELINES if c["id"] in only]
        groups = [to_run[i::4] for i in range(4)]
        groups = [g for g in groups if g]
    else:
        groups = [
            ["R4_P1_dream_kimi_rev", "R4_P4_parallel_dsh_gold_parity"],
            ["R4_P2_dream_ml4_rev", "R4_P5_parallel_pi_lean"],
            ["R4_P3_dream_dual_rev", "R4_P6_lean_pi_dual_rev"],
            ["R4_P7_minimax_m31_worker", "R4_P8_parallel_hetero_kimi_ds"],
        ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for f in [ex.submit(run_group, g) for g in groups]:
            f.result()
    results = []
    for c in PIPELINES:
        rp = f"{WORK_R4}/{c['id']}_result.json"
        if os.path.exists(rp):
            results.append(json.load(open(rp)))
    json.dump(results, open(f"{WORK_R4}/round4_pipelines_raw.json", "w"), indent=2)
    log("ALL_ROUND4_HERMETIC_PIPELINES_COMPLETE")
