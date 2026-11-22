import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import time

from run_round5_prompt_bakeoff import TASKS

REPO = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("WORK_R5_MODEL", "/private/tmp/bench_clean/r5_model_bakeoff"))
V3 = (REPO / "prompts/V3_caveman_adhd_winner.md").read_text()
SEED = 20261122

ARMS = {
    "abliterated_pr": {
        "provider": "paymentrequired",
        "model": "deepseek-v4.1-flash-abliterated",
    },
    "standard_1017_vercel": {
        "provider": "vercel",
        "model": "deepseek/deepseek-v4.1-flash-1017",
    },
    "ultrafast_1017_vercel": {
        "provider": "vercel",
        "model": "deepseek/deepseek-v4.1-flash-1017-ultrafast",
    },
}


def run_process(cmd, cwd, env, timeout):
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, 15)
            time.sleep(1)
            os.killpg(proc.pid, 9)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
        return -1, out, err + f"\nTIMEOUT after {timeout}s"


def hidden_test(task, work):
    eval_dir = Path(tempfile.mkdtemp(prefix="r5-model-hidden-"))
    try:
        for name in task["files"]:
            source = work / name
            if source.exists():
                shutil.copy2(source, eval_dir / name)
        test_file = eval_dir / "hidden_eval.py"
        test_file.write_text(task["eval"])
        result = subprocess.run(
            ["python3", "-m", "pytest", "-q", str(test_file)],
            cwd=eval_dir, capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0, (result.stdout + result.stderr)[-2000:]
    finally:
        shutil.rmtree(eval_dir, ignore_errors=True)


def count_loc(work, filenames):
    total = 0
    for name in filenames:
        path = work / name
        if path.exists():
            total += sum(
                1 for line in path.read_text(errors="ignore").splitlines()
                if line.strip() and not line.strip().startswith("#")
            )
    return total


def readiness(arm):
    if arm == "abliterated_pr":
        result = subprocess.run(
            ["pi", "auth", "check", "--provider", "paymentrequired"],
            capture_output=True, text=True,
        )
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    if os.environ.get("AI_GATEWAY_API_KEY"):
        return True, "AI_GATEWAY_API_KEY=SET"
    return False, "AI_GATEWAY_API_KEY=UNSET"


def run_cell(job, thinking):
    arm, task_id, repetition = job
    cid = f"{arm}__{task_id}__r{repetition}"
    work = OUT / "work" / cid
    work.mkdir(parents=True, exist_ok=True)
    task = TASKS[task_id]
    for name, content in task["files"].items():
        (work / name).write_text(content)
    spec = ARMS[arm]
    env = os.environ.copy()
    agent_dir = None
    if spec["provider"] == "vercel":
        agent_dir = Path(tempfile.mkdtemp(prefix="r5-vercel-"))
        models = {
            "providers": {
                "vercel": {
                    "baseUrl": "https://ai-gateway.vercel.sh/v1",
                    "apiKey": os.environ["AI_GATEWAY_API_KEY"],
                    "api": "openai-completions",
                    "models": [{
                        "id": spec["model"], "name": spec["model"], "reasoning": True,
                        "input": ["text"], "contextWindow": 1048576, "maxTokens": 32768,
                        "thinkingLevelMap": {
                            "off": "none", "minimal": "low", "low": "low",
                            "medium": "low", "high": "high", "xhigh": "max", "max": "max",
                        },
                    }],
                }
            }
        }
        (agent_dir / "models.json").write_text(json.dumps(models))
        (agent_dir / "settings.json").write_text("{}")
        (agent_dir / "trust.json").write_text("{}")
        (agent_dir / "APPEND_SYSTEM.md").write_text(V3)
        env["PI_CODING_AGENT_DIR"] = str(agent_dir)
    else:
        global_prompt = Path(os.path.expanduser("~/.pi/agent/APPEND_SYSTEM.md")).read_text()
        if global_prompt.strip() != V3.strip():
            raise RuntimeError("Global Pi prompt no longer matches controlled V3 baseline")
    cmd = [
        "pi", "-p", "--mode", "json", "--no-session", "--no-context-files",
        "--no-extensions", "--no-mcp", "--no-skills",
        "--provider", spec["provider"], "--model", spec["model"],
        "--thinking", thinking, "--", task["prompt"],
    ]
    started = time.time()
    try:
        rc, stdout, stderr = run_process(cmd, str(work), env, 180)
    finally:
        if agent_dir:
            shutil.rmtree(agent_dir, ignore_errors=True)
    elapsed = round(time.time() - started, 2)
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    (OUT / "raw" / f"{cid}.stdout.jsonl").write_text(stdout)
    (OUT / "raw" / f"{cid}.stderr.txt").write_text(stderr)
    usage = {
        "turns": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0,
        "reasoning_tokens": 0, "total_tokens": 0, "cost_usd": 0,
    }
    final_text = ""
    error = ""
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "message_end" and event.get("message", {}).get("errorMessage"):
            error = event["message"]["errorMessage"]
        if event.get("type") != "turn_end":
            continue
        message = event.get("message", {})
        data = message.get("usage") or {}
        usage["turns"] += 1
        usage["tool_calls"] += len(event.get("toolResults") or [])
        usage["input_tokens"] += data.get("input", 0) + data.get("cacheRead", 0)
        usage["output_tokens"] += data.get("output", 0)
        usage["reasoning_tokens"] += data.get("reasoning", 0)
        usage["total_tokens"] += data.get("totalTokens", 0)
        usage["cost_usd"] += (data.get("cost") or {}).get("total", 0)
        texts = [c.get("text", "") for c in message.get("content", []) if c.get("type") == "text"]
        if texts:
            final_text = "\n".join(texts)
    passed, detail = hidden_test(task, work)
    result = {
        "id": cid, "arm": arm, "provider": spec["provider"], "model": spec["model"],
        "task": task_id, "repetition": repetition, "thinking": thinking,
        "rc": rc, "passed": passed, "elapsed_s": elapsed, "final_text": final_text,
        "code_loc": count_loc(work, list(task["files"])), "eval_detail": detail,
        "error": error, "stderr": stderr[-1000:], "work_dir": str(work), **usage,
    }
    result["end_to_end_output_tok_s"] = round(usage["output_tokens"] / elapsed, 2) if elapsed else None
    with open(OUT / "results.jsonl", "a") as handle:
        handle.write(json.dumps(result) + "\n")
    print(
        f"{cid} pass={passed} rc={rc} tok={result['total_tokens']} "
        f"out={result['output_tokens']} wall={elapsed}s", flush=True,
    )
    return result


def aggregate(results):
    grouped = {}
    for arm in ARMS:
        rows = [r for r in results if r["arm"] == arm]
        if not rows:
            continue
        passes = sum(r["passed"] for r in rows)
        pass_rate = passes / len(rows)
        mean_tokens = sum(r["total_tokens"] for r in rows) / len(rows)
        mean_wall = sum(r["elapsed_s"] for r in rows) / len(rows)
        grouped[arm] = {
            "runs": len(rows), "passes": passes, "pass_rate": pass_rate,
            "mean_total_tokens": round(mean_tokens, 1),
            "mean_output_tokens": round(sum(r["output_tokens"] for r in rows) / len(rows), 1),
            "mean_wall_s": round(mean_wall, 2),
            "mean_end_to_end_output_tok_s": round(sum(r["end_to_end_output_tok_s"] for r in rows) / len(rows), 2),
            "mean_code_loc": round(sum(r["code_loc"] for r in rows) / len(rows), 1),
            "expected_tokens_per_pass": round(mean_tokens / pass_rate, 1) if pass_rate else None,
            "expected_wall_s_per_pass": round(mean_wall / pass_rate, 2) if pass_rate else None,
            "reported_cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
        }
    output = {"seed": SEED, "arms": grouped}
    (OUT / "summary.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=list(ARMS), choices=list(ARMS))
    parser.add_argument("--tasks", nargs="*", default=list(TASKS), choices=list(TASKS))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--thinking", default="high")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    states = {arm: readiness(arm) for arm in args.models}
    for arm, (_, detail) in states.items():
        print(f"{arm}: {detail}", flush=True)
    if args.check:
        raise SystemExit(0 if all(ok for ok, _ in states.values()) else 1)
    selected = [arm for arm in args.models if states[arm][0]]
    skipped = [arm for arm in args.models if not states[arm][0]]
    if skipped:
        print(f"Skipping unavailable arms: {', '.join(skipped)}", flush=True)
    if not selected:
        raise SystemExit("No requested model arms are ready")
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(a, t, r) for a in selected for t in args.tasks for r in range(1, args.repetitions + 1)]
    random.Random(SEED).shuffle(jobs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run_cell, jobs, [args.thinking] * len(jobs)))
    aggregate(results)
