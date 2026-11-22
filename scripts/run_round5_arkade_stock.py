import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path("/private/tmp/bench_clean/r5_arkade_stock")
BASE_REPO = Path("/private/tmp/bench_clean/base_repo")
BASE_NODE_MODULES = Path("/private/tmp/bench_clean/base_node_modules")
TASK = Path("/tmp/subtasks/st3_gold/TASK_PROMPT.md").read_text()
MODEL = "kimi-code/k3.1-pro-highspeed"

spec = importlib.util.spec_from_file_location("round4", Path(__file__).with_name("run_round4_beat_gold.py"))
r4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r4)
r4.WORK_R4 = str(ROOT)

gate_source = Path("/tmp/subtasks/eval_blind_st4.py").read_text().split("cids = [")[0]
gate_ns = {}
exec(gate_source, gate_ns)
run_gates = gate_ns["run_deterministic_gates"]


def setup_attempt(effort, repetition):
    wt = ROOT / f"wt_stock__{effort}__r{repetition}"
    if wt.exists():
        shutil.rmtree(wt)
    subprocess.run(["git", "clone", "-q", str(BASE_REPO), str(wt)], check=True)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=wt, check=True)
    os.symlink(BASE_NODE_MODULES, wt / "node_modules")
    return wt


def clean_diff(wt):
    subprocess.run(["git", "add", "-N", "."], cwd=wt, check=True)
    subprocess.run(["git", "reset", "-q", "--", "node_modules"], cwd=wt, check=True)
    return subprocess.run(["git", "diff", "--", ":!node_modules"], cwd=wt, capture_output=True, text=True, check=True).stdout


def run_attempt(effort, repetition, timeout):
    cid = f"stock__{effort}__r{repetition}"
    wt = setup_attempt(effort, repetition)
    started = time.time()
    print(f"[{cid}] START", flush=True)
    stage = r4.run_kimi_cli(
        MODEL, TASK, str(wt), timeout=timeout,
        system_prompt="", thinking_effort=effort,
    )
    diff = clean_diff(wt)
    (ROOT / f"{cid}.patch").write_text(diff)
    result = {
        "id": cid, "model": MODEL, "thinking_effort": effort,
        "prompt": "stock_no_custom_instructions", "repetition": repetition,
        "wall_s": round(time.time() - started, 2),
        "added_loc": sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++") and line[1:].strip()),
        "stage": stage,
    }
    print(f"[{cid}] AGENT_DONE rc={stage['rc']} tokens={stage['total_tokens']} wall={result['wall_s']}s", flush=True)
    result["gates"] = run_gates(str(wt))
    (ROOT / f"{cid}_result.json").write_text(json.dumps(result, indent=2))
    print(f"[{cid}] GATES {result['gates']['gates_passed']}/7", flush=True)
    return result


def aggregate(results):
    arms = {}
    for effort in sorted(set(r["thinking_effort"] for r in results)):
        rows = [r for r in results if r["thinking_effort"] == effort]
        token_rows = [r for r in rows if r["stage"]["total_tokens"] > 0]
        arms[effort] = {
            "runs": len(rows),
            "mean_gates": round(sum(r["gates"]["gates_passed"] for r in rows) / len(rows), 2),
            "all_7_count": sum(r["gates"]["gates_passed"] == 7 for r in rows),
            "own_tests_passes": sum(r["gates"]["G1_own_tests"] for r in rows),
            "mean_wall_s": round(sum(r["wall_s"] for r in rows) / len(rows), 2),
            "mean_added_loc": round(sum(r["added_loc"] for r in rows) / len(rows), 1),
            "token_runs": len(token_rows),
            "mean_total_tokens": round(sum(r["stage"]["total_tokens"] for r in token_rows) / len(token_rows), 1) if token_rows else None,
            "mean_output_tokens": round(sum(r["stage"]["output_tokens"] for r in token_rows) / len(token_rows), 1) if token_rows else None,
        }
    output = {"model": MODEL, "prompt": "stock_no_custom_instructions", "arms": arms}
    (ROOT / "summary.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--efforts", nargs="*", default=["low", "high", "max"], choices=["low", "high", "max"])
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for effort in args.efforts:
        for repetition in range(1, args.repetitions + 1):
            result_file = ROOT / f"stock__{effort}__r{repetition}_result.json"
            if result_file.exists():
                results.append(json.loads(result_file.read_text()))
            else:
                results.append(run_attempt(effort, repetition, args.timeout))
    aggregate(results)
