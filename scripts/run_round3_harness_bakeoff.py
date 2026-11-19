import os, sys, json, time, glob, signal, shutil, tempfile, subprocess, concurrent.futures

WORK_R3 = "/tmp/subtasks/st6_round3"
WORK_ST3 = "/tmp/subtasks/st3_gold"
WORK_ST4 = "/tmp/subtasks/st4_bakeoff"
NURI_REPO = "/Users/eminmahrt/Developer/nuri-server-musig2-v4-arkade"
ORIGIN_SHA = "136a54faa0c1af817cf9f829412582291a7ec83f"

os.makedirs(WORK_R3, exist_ok=True)
os.makedirs("/tmp/subtasks/logs", exist_ok=True)
LOG = open("/tmp/subtasks/logs/st6_round3.log", "w", buffering=1)

V3_SKILL = open("/Users/eminmahrt/Developer/agent-prompt-brevity-bench/prompts/V3_caveman_adhd_winner.md").read()
TASK_PROMPT = open(f"{WORK_ST3}/TASK_PROMPT.md").read()

st4_provs = json.load(open(f"{WORK_ST4}/models.json"))["providers"]
NOUS_KEY = st4_provs["nous"]["apiKey"]
PR_KEY = st4_provs["paymentrequired"]["apiKey"]

def log(msg):
    LOG.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(msg, flush=True)

def run_cmd_pg(cmd, cwd, env, timeout):
    t0 = time.time()
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True
    )
    try:
        out_s, err_s = proc.communicate(timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            time.sleep(1.5)
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass
        out_s, err_s = proc.communicate()
        rc = -1
        err_s = (err_s or "") + f"\nTIMEOUT after {timeout}s"
    return rc, out_s or "", (err_s or "")[-500:], round(time.time() - t0, 2)

# --- HARNESS 1: pi (1.5.2) ---
def run_pi(provider, model, prompt, cwd, tools=True, timeout=540):
    ag = tempfile.mkdtemp(prefix="r3-pi-")
    try:
        models_doc = {
            "providers": {
                "nous": {
                    "baseUrl": "https://inference-api.nousresearch.com/v1",
                    "apiKey": NOUS_KEY,
                    "api": "openai-completions",
                    "models": [
                        {"id": "moonshotai/kimi-k3.1-pro", "name": "kimi-k3.1-pro", "reasoning": True, "input": ["text"], "contextWindow": 262144, "maxTokens": 32768},
                        {"id": "mistralai/mistral-large-4-0", "name": "mistral-large-4-0", "reasoning": True, "input": ["text"], "contextWindow": 262144, "maxTokens": 32768},
                        {"id": "qwen/qwen4-max", "name": "qwen4-max", "reasoning": True, "input": ["text"], "contextWindow": 262144, "maxTokens": 32768},
                        {"id": "anthropic/claude-fable-5.2", "name": "claude-fable-5.2", "reasoning": True, "input": ["text"], "contextWindow": 262144, "maxTokens": 32768},
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
        rc, out_s, err_s, elapsed = run_cmd_pg(cmd, cwd, env, timeout)
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

# --- HARNESS 2: dsh (DeepSeek Harness 0.2.1-rc.5) ---
def run_dsh(provider, model, prompt, cwd, tools=True, timeout=540):
    patch_f = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False)
    v3_indented = V3_SKILL.replace("\n", "\n      ")
    disable_tools_block = ""
    if not tools:
        disable_tools_block = """
- id: tool-bash
  disabled: true
- id: tool-pwsh
  disabled: true
- id: tool-jobs
  disabled: true
- id: tool-fs
  disabled: true
- id: tool-fs-search
  disabled: true
- id: tool-subagent
  disabled: true
- id: tool-subagent-fork
  disabled: true
- id: tool-workflow
  disabled: true
- id: tool-web
  disabled: true
"""
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
          - id: moonshotai/kimi-k3.1-pro
            contextWindow: 1048576
          - id: mistralai/mistral-large-4-0
            contextWindow: 1048576
          - id: deepseek/deepseek-v4.1-flash-1017
            contextWindow: 1048576
{disable_tools_block}
""")
    patch_f.close()
    try:
        env = os.environ.copy()
        env["ROUTER_INTERNAL_KEY"] = PR_KEY
        env["NOUS_API_KEY"] = NOUS_KEY
        env["DSH_PERMISSION_MODE"] = "danger-full-access"
        cmd = ["/Users/eminmahrt/.volta/bin/dsh", "--profile", "headless", "--patch", patch_f.name, "--json", prompt]
        rc, out_s, err_s, elapsed = run_cmd_pg(cmd, cwd, env, timeout)
        tot_tok = in_tok = out_tok = rsn_tok = steps = tool_calls = 0
        final_txt = ""
        last_text = ""
        for line in out_s.splitlines():
            if not line.strip().startswith("{"): continue
            try: ev = json.loads(line)
            except Exception: continue
            tp = ev.get("type")
            if tp == "tool_call":
                tool_calls += 1
            elif tp == "text":
                last_text = ev.get("text", "")
            elif tp == "final":
                if ev.get("text"): final_txt = ev.get("text", "")
            elif tp == "status" and ev.get("phase") == "step_end":
                steps += 1
                u = ev.get("usage") or {}
                it = u.get("inputTokens", 0)
                cr = u.get("cacheReadTokens", 0)
                ot = u.get("outputTokens", 0)
                tt = u.get("totalTokens") or (it + cr + ot)
                in_tok += (it + cr)
                out_tok += ot
                tot_tok += tt
        if not final_txt:
            final_txt = last_text
        return {
            "harness": "dsh-0.2.1-rc.5", "model": f"{provider}/{model}", "rc": rc, "elapsed_s": elapsed,
            "turns": steps, "tool_calls": tool_calls,
            "total_tokens": tot_tok, "input_tokens": in_tok, "output_tokens": out_tok, "reasoning_tokens": rsn_tok,
            "text": final_txt, "stderr": err_s
        }
    finally:
        if os.path.exists(patch_f.name):
            os.unlink(patch_f.name)

# --- HARNESS 3: kimi (Kimi Code CLI 2.5.2) ---
def run_kimi_cli(model_alias, prompt, cwd, timeout=540):
    empty_skills = tempfile.mkdtemp(prefix="r3-kimi-skills-")
    try:
        env = os.environ.copy()
        full_prompt = f"{V3_SKILL}\n\n{prompt}"
        cmd = [
            "/Users/eminmahrt/.kimi-code/bin/kimi",
            "--skills-dir", empty_skills,
            "--model", model_alias,
            "--output-format", "stream-json",
            "-p", full_prompt
        ]
        rc, out_s, err_s, elapsed = run_cmd_pg(cmd, cwd, env, timeout)
        tot_tok = in_tok = out_tok = rsn_tok = steps = tool_calls = 0
        final_txt = ""
        session_id = ""
        for line in out_s.splitlines():
            if not line.strip().startswith("{"): continue
            try: ev = json.loads(line)
            except Exception: continue
            if ev.get("role") == "assistant":
                tcs = ev.get("tool_calls") or []
                tool_calls += len(tcs)
                if ev.get("content"):
                    final_txt = ev.get("content", "")
            elif ev.get("type") == "session.resume_hint":
                session_id = ev.get("session_id", "")
        # Read exact token usage from Kimi's wire.jsonl session file!
        if session_id:
            smatches = glob.glob(os.path.expanduser(f"~/.kimi-code/sessions/**/{session_id}/agents/*/wire.jsonl"), recursive=True)
            for wf in smatches:
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

# --- HARNESS 4: vibe (Mistral Vibe 3.1.3) ---
def run_vibe(model, prompt, cwd, tools=True, timeout=540):
    vibe_home = tempfile.mkdtemp(prefix="r3-vibe-home-")
    vibe_out = tempfile.mkdtemp(prefix="r3-vibe-out-")
    try:
        disabled_tools_line = 'disabled_tools = ["*"]' if not tools else 'disabled_tools = []'
        open(f"{vibe_home}/config.toml", "w").write(f"""
active_model = "target"
enable_telemetry = false
enable_update_checks = false
enable_auto_update = false
skill_paths = []
disabled_skills = ["*"]
{disabled_tools_line}

[[providers]]
name = "nous"
api_base = "https://inference-api.nousresearch.com/v1"
api_key_env_var = "NOUS_API_KEY"
api_style = "openai"
backend = "generic"

[[models]]
name = "{model}"
provider = "nous"
alias = "target"
max_context_length = 262144
thinking = true
""")
        env = os.environ.copy()
        env["VIBE_HOME"] = vibe_home
        env["NOUS_API_KEY"] = NOUS_KEY
        cmd = [
            "/Users/eminmahrt/.local/bin/vibe",
            "--workdir", cwd, "--trust", "--auto-approve",
            "--model", "target", "--thinking", "high",
            "--time-limit", str(max(30, timeout - 10)),
            "--output", "json", "--output-dir", vibe_out,
            "-p", f"{V3_SKILL}\n\n{prompt}"
        ]
        rc, out_s, err_s, elapsed = run_cmd_pg(cmd, cwd, env, timeout + 15)
        tot_tok = in_tok = out_tok = rsn_tok = steps = tool_calls = 0
        final_txt = ""
        exp_p = f"{vibe_out}/export.json"
        if os.path.exists(exp_p):
            exp = json.load(open(exp_p))
            u = exp.get("usage") or {}
            in_tok = u.get("input_tokens", 0)
            out_tok = u.get("output_tokens", 0)
            tot_tok = u.get("total_tokens", in_tok + out_tok)
            steps = exp.get("steps", 0) if isinstance(exp.get("steps"), int) else len(exp.get("steps") or [])
        if out_s.strip().startswith("["):
            try:
                arr = json.loads(out_s)
                for item in arr:
                    role = item.get("role") or (item.get("message") or {}).get("role")
                    msg_c = item.get("content") or (item.get("message") or {}).get("content")
                    tcs = item.get("tool_calls") or (item.get("message") or {}).get("tool_calls") or []
                    tool_calls += len(tcs)
                    if role == "assistant":
                        if isinstance(msg_c, str) and msg_c.strip():
                            final_txt = msg_c
                        elif isinstance(msg_c, list):
                            txts = [x.get("text", "") for x in msg_c if isinstance(x, dict) and x.get("type") == "text" and x.get("text")]
                            if txts: final_txt = "\n".join(txts)
            except Exception:
                pass
        return {
            "harness": "mistral-vibe-3.1.3", "model": f"nous/{model}", "rc": rc, "elapsed_s": elapsed,
            "turns": steps, "tool_calls": tool_calls,
            "total_tokens": tot_tok, "input_tokens": in_tok, "output_tokens": out_tok, "reasoning_tokens": rsn_tok,
            "text": final_txt, "stderr": err_s
        }
    finally:
        shutil.rmtree(vibe_home, ignore_errors=True)
        shutil.rmtree(vibe_out, ignore_errors=True)

# --- HARNESS 5: opencode (1.19.3) ---
def run_opencode(provider_model, prompt, cwd, timeout=540):
    oc_dir = tempfile.mkdtemp(prefix="r3-oc-")
    try:
        oc_json = f"{oc_dir}/opencode.json"
        json.dump({
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "nous": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Nous",
                    "options": {"baseURL": "https://inference-api.nousresearch.com/v1", "apiKey": "{env:NOUS_API_KEY}"},
                    "models": {
                        "moonshotai/kimi-k3.1-pro": {"name": "Kimi K3.1 Pro", "limit": {"context": 262144, "output": 32768}},
                        "mistralai/mistral-large-4-0": {"name": "Mistral Large 4", "limit": {"context": 262144, "output": 32768}},
                    }
                },
                "pr": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "PR",
                    "options": {"baseURL": "https://router.paymentrequired.com/v1/internal", "apiKey": "{env:ROUTER_INTERNAL_KEY}"},
                    "models": {
                        "deepseek-v4.1-flash-abliterated": {"name": "DeepSeek V4.1 Flash", "limit": {"context": 262144, "output": 32768}}
                    }
                }
            }
        }, open(oc_json, "w"))
        env = os.environ.copy()
        env["OPENCODE_CONFIG"] = oc_json
        env["NOUS_API_KEY"] = NOUS_KEY
        env["ROUTER_INTERNAL_KEY"] = PR_KEY
        cmd = [
            "/Users/eminmahrt/.local/bin/opencode", "run",
            "--pure", "--auto", "--format", "json",
            "--dir", cwd, "-m", provider_model,
            f"{V3_SKILL}\n\n{prompt}"
        ]
        rc, out_s, err_s, elapsed = run_cmd_pg(cmd, cwd, env, timeout)
        tot_tok = in_tok = out_tok = rsn_tok = steps = tool_calls = 0
        final_txt = ""
        for line in out_s.splitlines():
            if not line.strip().startswith("{"): continue
            try: ev = json.loads(line)
            except Exception: continue
            tp = ev.get("type")
            part = ev.get("part") or {}
            if tp == "tool_use":
                tool_calls += 1
            elif tp == "text" and part.get("text"):
                final_txt = part.get("text", "")
            elif tp == "step_finish":
                steps += 1
                toks = part.get("tokens") or {}
                in_tok += toks.get("input", 0) + (toks.get("cache") or {}).get("read", 0)
                out_tok += toks.get("output", 0)
                rsn_tok += toks.get("reasoning", 0)
                tot_tok += toks.get("total", 0)
        return {
            "harness": "opencode-1.19.3", "model": provider_model, "rc": rc, "elapsed_s": elapsed,
            "turns": steps, "tool_calls": tool_calls,
            "total_tokens": tot_tok, "input_tokens": in_tok, "output_tokens": out_tok, "reasoning_tokens": rsn_tok,
            "text": final_txt, "stderr": err_s
        }
    finally:
        shutil.rmtree(oc_dir, ignore_errors=True)

def dispatch_agent(spec, prompt, cwd, tools=True, timeout=540):
    h = spec["harness"]
    if h == "pi":
        return run_pi(spec["provider"], spec["model"], prompt, cwd, tools=tools, timeout=timeout)
    elif h == "dsh":
        return run_dsh(spec["provider"], spec["model"], prompt, cwd, tools=tools, timeout=timeout)
    elif h == "kimi":
        return run_kimi_cli(spec["model"], prompt, cwd, timeout=timeout)
    elif h == "vibe":
        return run_vibe(spec["model"], prompt, cwd, tools=tools, timeout=timeout)
    elif h == "opencode":
        return run_opencode(f"{spec['provider']}/{spec['model']}", prompt, cwd, timeout=timeout)
    raise ValueError(f"Unknown harness {h}")

PIPELINES = [
    {
        "id": "R3_H1_kimi_cli_k3_hs",
        "label": "Solo Native Harness: kimi-code 2.5.2 + kimi-code/k3.1-pro-highspeed",
        "open_weights": True,
        "mode": "solo",
        "worker": {"harness": "kimi", "model": "kimi-code/k3.1-pro-highspeed"}
    },
    {
        "id": "R3_H2_pi_k3_nous",
        "label": "Solo Generic pi Harness (Fast Control): pi 1.5.2 + nous/kimi-k3.1-pro (133 tok/s)",
        "open_weights": True,
        "mode": "solo",
        "worker": {"harness": "pi", "provider": "nous", "model": "moonshotai/kimi-k3.1-pro"}
    },
    {
        "id": "R3_H3_opencode_k3_nous",
        "label": "Solo Opencode Harness: opencode 1.19.3 + nous/kimi-k3.1-pro",
        "open_weights": True,
        "mode": "solo",
        "worker": {"harness": "opencode", "provider": "nous", "model": "moonshotai/kimi-k3.1-pro"}
    },
    {
        "id": "R3_H4_dsh_k3_nous",
        "label": "Solo DeepSeek Harness on Kimi: dsh 0.2.1 + nous/kimi-k3.1-pro",
        "open_weights": True,
        "mode": "solo",
        "worker": {"harness": "dsh", "provider": "nous", "model": "moonshotai/kimi-k3.1-pro"}
    },
    {
        "id": "R3_H5_dsh_ds_v4_1_fast",
        "label": "Solo Native DeepSeek Harness: dsh 0.2.1 + deepseek-v4.1-flash (153 tok/s)",
        "open_weights": True,
        "mode": "solo",
        "worker": {"harness": "dsh", "provider": "402router", "model": "deepseek-v4.1-flash-abliterated"}
    },
    {
        "id": "R3_H6_opencode_ds_v4_1_fast",
        "label": "Solo Opencode Harness on DeepSeek: opencode 1.19.3 + deepseek-v4.1-flash (153 tok/s)",
        "open_weights": True,
        "mode": "solo",
        "worker": {"harness": "opencode", "provider": "pr", "model": "deepseek-v4.1-flash-abliterated"}
    },
    {
        "id": "R3_H7_vibe_ml4_native",
        "label": "Solo Native Mistral Vibe Harness: vibe 3.1.3 + mistral-large-4-0",
        "open_weights": True,
        "mode": "solo",
        "worker": {"harness": "vibe", "model": "mistralai/mistral-large-4-0"}
    },
    {
        "id": "R3_H8_combo_native_dream_team",
        "label": "Multi-Harness Native Dream Team: kimi-cli(k3.1-pro-hs) -> dsh(ds-v4.1-flash) -> vibe(ml4) -> dsh(ds-v4.1-flash)",
        "open_weights": True,
        "mode": "pipeline",
        "planner": {"harness": "kimi", "model": "kimi-code/k3.1-pro-highspeed"},
        "worker": {"harness": "dsh", "provider": "402router", "model": "deepseek-v4.1-flash-abliterated"},
        "reviewer": {"harness": "vibe", "model": "mistralai/mistral-large-4-0"},
        "orchestrator": {"harness": "dsh", "provider": "402router", "model": "deepseek-v4.1-flash-abliterated"}
    },
    {
        "id": "R3_H9_combo_dsh_unified",
        "label": "Unified DSH Multi-Brain Stack: dsh(k3.1-pro) -> dsh(ds-v4.1-flash) -> dsh(ml4) -> dsh(ds-v4.1-flash)",
        "open_weights": True,
        "mode": "pipeline",
        "planner": {"harness": "dsh", "provider": "nous", "model": "moonshotai/kimi-k3.1-pro"},
        "worker": {"harness": "dsh", "provider": "402router", "model": "deepseek-v4.1-flash-abliterated"},
        "reviewer": {"harness": "dsh", "provider": "nous", "model": "mistralai/mistral-large-4-0"},
        "orchestrator": {"harness": "dsh", "provider": "402router", "model": "deepseek-v4.1-flash-abliterated"}
    },
    {
        "id": "R3_H10_combo_qwen4_dsh",
        "label": "Qwen4-Max + Native DSH Combo: pi(qwen4-max) -> dsh(ds-v4.1-flash) -> pi(qwen4-max) -> dsh(ds-v4.1-flash)",
        "open_weights": False,
        "mode": "pipeline",
        "planner": {"harness": "pi", "provider": "nous", "model": "qwen/qwen4-max"},
        "worker": {"harness": "dsh", "provider": "402router", "model": "deepseek-v4.1-flash-abliterated"},
        "reviewer": {"harness": "pi", "provider": "nous", "model": "qwen/qwen4-max"},
        "orchestrator": {"harness": "dsh", "provider": "402router", "model": "deepseek-v4.1-flash-abliterated"}
    }
]

def setup_wt(cid):
    wt = f"{WORK_R3}/wt_{cid}"
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
        s_work = dispatch_agent(cfg["worker"], TASK_PROMPT, cwd=wt, tools=True, timeout=600)
        s_work["stage"] = "solo_worker"
        stages.append(s_work)
    else:
        plan_prompt = f"""ROLE: Planner / Architect. Do NOT edit files. Inspect only exact relevant lines in `src/ArkadeServer.js`, `src/ArkadeConfig.js`, `src/ArkadeNotifications.js`, `ENDPOINTS.md`, and output a tight atomic implementation blueprint (<350 words) for the Worker covering file edits, exact line numbers/helpers to reuse (`verifyRequestAuth`, `getClientSignerFromToken`, `getDerivedServerPublicKey`, `deriveAggregatedPk33`), JCS SHA-256 IDs, BIP-68 CSV encoding traps, and security checks.

TASK:
{TASK_PROMPT}"""
        s_plan = dispatch_agent(cfg["planner"], plan_prompt, cwd=wt, tools=True, timeout=360)
        s_plan["stage"] = "planner"
        stages.append(s_plan)
        log(f"[{cid}] Planner ({s_plan['harness']}:{s_plan['model']}) done: {s_plan['total_tokens']} tok, {s_plan['elapsed_s']}s")

        work_prompt = f"""ROLE: Worker. Implement the task completely and run `node --test src/ArkadeExecutorClient.test.js` until green.

PLANNER BLUEPRINT:
{s_plan['text']}

EXACT TASK SPECIFICATION:
{TASK_PROMPT}"""
        s_work = dispatch_agent(cfg["worker"], work_prompt, cwd=wt, tools=True, timeout=540)
        s_work["stage"] = "worker"
        stages.append(s_work)
        log(f"[{cid}] Worker ({s_work['harness']}:{s_work['model']}) done: {s_work['total_tokens']} tok, {s_work['elapsed_s']}s")

        cand_diff = clean_wt_diff(wt)
        test_mid = subprocess.run(["node", "--test", "src/ArkadeExecutorClient.test.js"], cwd=wt, capture_output=True, text=True, timeout=60)
        rev_prompt = f"""ROLE: Adversarial Security & Protocol Reviewer. You have NO file tools; the complete candidate git diff and test output are provided inline below—analyze them directly right now! List ONLY real bugs, security bypasses (ownership/IDOR, purpose-scoped token, admin port `:7081` / `/v1/admin` / HTTP redirect leak, URL/secret leak in logs), encoding errors (`encodeScriptNumHex`, BIP-68 seconds % 512 & bit-22, JCS SHA-256), or missing deliverables. If zero issues, reply `APPROVED_NO_FIXES`.

TASK SPEC:
{TASK_PROMPT}

TEST OUTPUT (rc={test_mid.returncode}):
{(test_mid.stdout + test_mid.stderr)[-2000:]}

GIT DIFF:
```diff
{cand_diff[:38000]}
```"""
        s_rev = dispatch_agent(cfg["reviewer"], rev_prompt, cwd=wt, tools=False, timeout=300)
        s_rev["stage"] = "reviewer"
        stages.append(s_rev)
        log(f"[{cid}] Reviewer ({s_rev['harness']}:{s_rev['model']}) done: {s_rev['total_tokens']} tok, {s_rev['elapsed_s']}s | verdict={s_rev['text'][:80].replace(chr(10),' ')}")

        if "APPROVED_NO_FIXES" not in s_rev["text"] or test_mid.returncode != 0:
            orch_prompt = f"""ROLE: Orchestrator / Finisher. Verify each Reviewer finding below; apply real fixes with minimal code changes and ensure `node --test src/ArkadeExecutorClient.test.js` exits 0.

REVIEWER FINDINGS:
{s_rev['text']}"""
            s_orch = dispatch_agent(cfg["orchestrator"], orch_prompt, cwd=wt, tools=True, timeout=360)
            s_orch["stage"] = "orchestrator_fix"
            stages.append(s_orch)
            log(f"[{cid}] Orchestrator ({s_orch['harness']}:{s_orch['model']}) done: {s_orch['total_tokens']} tok, {s_orch['elapsed_s']}s")

    wall_s = round(time.time() - t_start, 2)
    final_diff = clean_wt_diff(wt)
    open(f"{WORK_R3}/{cid}.patch", "w").write(final_diff)

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
    json.dump(res, open(f"{WORK_R3}/{cid}_result.json", "w"), indent=2)
    log(f"[{cid}] COMPLETE: own_tests={own_ok} tot_tok={res['total_tokens']} wall={wall_s}s added_loc={added_loc}")
    return res

def run_group(cids):
    out = []
    for c in [p for p in PIPELINES if p["id"] in cids]:
        out.append(run_pipeline(c))
    return out

if __name__ == "__main__":
    # 5 balanced groups across distinct endpoints/harnesses to avoid rate-limit contention:
    groups = [
        ["R3_H1_kimi_cli_k3_hs", "R3_H8_combo_native_dream_team"],
        ["R3_H5_dsh_ds_v4_1_fast", "R3_H9_combo_dsh_unified"],
        ["R3_H6_opencode_ds_v4_1_fast", "R3_H10_combo_qwen4_dsh"],
        ["R3_H2_pi_k3_nous", "R3_H4_dsh_k3_nous"],
        ["R3_H7_vibe_ml4_native", "R3_H3_opencode_k3_nous"],
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(run_group, g) for g in groups]
        results = []
        for f in futs:
            results.extend(f.result())
    json.dump(results, open(f"{WORK_R3}/round3_pipelines_raw.json", "w"), indent=2)
    log("ALL_10_ROUND3_PIPELINES_COMPLETE")
