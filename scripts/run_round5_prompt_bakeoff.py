import argparse
import concurrent.futures
import glob
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import time

REPO = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("WORK_R5_PROMPT", "/private/tmp/bench_clean/r5_prompt_bakeoff"))
KIMI = os.path.expanduser("~/.kimi-code/bin/kimi")
MODEL = "kimi-code/k3.1-pro-highspeed"
SEED = 20261122
BASE_SYSTEM_TEMPLATE = None

VARIANTS = {
    "V0_stock": "",
    "V3_caveman_adhd": (REPO / "prompts/V3_caveman_adhd_winner.md").read_text(),
    "V4a_tldr_caveman": (REPO / "prompts/V4a_tldr_caveman.md").read_text(),
    "V4b_tldr_think_budget": (REPO / "prompts/V4b_tldr_think_budget.md").read_text(),
}

T1_FILES = {
    "retry_util.py": '''import time

def retry_call(fn, retries=3, base_delay=0.01, retry_on=(Exception,), sleep_fn=time.sleep):
    """Call fn(). Retry up to `retries` additional times on `retry_on` exceptions
    with exponential backoff: base_delay * (2 ** attempt).
    Raise ValueError if retries < 0 or base_delay < 0.
    Never retry on KeyboardInterrupt or SystemExit even if Exception is in retry_on (note BaseException)."""
    attempt = 0
    delays = []
    while attempt < retries:
        try:
            return fn()
        except Exception as exc:
            sleep_fn(base_delay * attempt)
            attempt += 1
    return None
'''
}

T1_EVAL = '''import pytest
from retry_util import retry_call

def test_success_first_try():
    calls = 0
    def ok():
        nonlocal calls
        calls += 1
        return "done"
    assert retry_call(ok) == "done"
    assert calls == 1

def test_retries_zero_runs_once_and_raises():
    with pytest.raises(RuntimeError, match="boom"):
        retry_call(lambda: (_ for _ in ()).throw(RuntimeError("boom")), retries=0, sleep_fn=lambda _: None)

def test_exponential_backoff_and_eventual_success():
    sleeps = []
    calls = 0
    def flaky():
        nonlocal calls
        calls += 1
        if calls < 4:
            raise ConnectionError("temp")
        return 99
    assert retry_call(flaky, retries=3, base_delay=0.5, retry_on=(ConnectionError,), sleep_fn=sleeps.append) == 99
    assert calls == 4
    assert sleeps == [0.5, 1.0, 2.0]

def test_exhausted_raises_last_exception():
    sleeps = []
    calls = 0
    def always_fail():
        nonlocal calls
        calls += 1
        raise ValueError(f"fail-{calls}")
    with pytest.raises(ValueError, match="fail-3"):
        retry_call(always_fail, retries=2, base_delay=1.0, sleep_fn=sleeps.append)
    assert calls == 3
    assert sleeps == [1.0, 2.0]

def test_unmatched_exception_not_retried():
    calls = 0
    def bad_type():
        nonlocal calls
        calls += 1
        raise KeyError("nope")
    with pytest.raises(KeyError):
        retry_call(bad_type, retries=3, retry_on=(ValueError,), sleep_fn=lambda _: None)
    assert calls == 1

@pytest.mark.parametrize("kwargs", [{"retries": -1}, {"base_delay": -0.1}])
def test_negative_args_validation(kwargs):
    with pytest.raises(ValueError):
        retry_call(lambda: 1, **kwargs)

@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_base_exceptions_never_retried(exc_type):
    calls = 0
    def stop():
        nonlocal calls
        calls += 1
        raise exc_type()
    with pytest.raises(exc_type):
        retry_call(stop, retries=3, sleep_fn=lambda _: None)
    assert calls == 1
'''

T2_FILES = {
    "duration.py": '''# Implement parse_duration(s: str) -> float returning total seconds.
# Requirements:
# - Supports units: ms (0.001), s (1), m (60), h (3600), d (86400).
# - Supports chained units like "1h30m", "2m 15s", "500ms", "1.5h", "+2m", "-30s" (leading sign applies to whole duration).
# - Case-insensitive units ("1H30M" == 5400.0), surrounding whitespace ignored.
# - Reject empty string, bare numbers without unit ("42"), unknown units ("5w"), duplicate/misplaced signs ("1h-30m"), or garbage with ValueError.
'''
}

T2_EVAL = '''import pytest
from duration import parse_duration

@pytest.mark.parametrize("text,expected", [
    ("500ms", 0.5), ("10s", 10.0), ("2m", 120.0),
    ("1.5h", 5400.0), ("1d", 86400.0), ("  1h30m ", 5400.0),
    ("2m 15s 500ms", 135.5), ("1H30M", 5400.0),
    ("+2m", 120.0), ("-1m30s", -90.0),
])
def test_valid(text, expected):
    assert parse_duration(text) == pytest.approx(expected)

@pytest.mark.parametrize("bad", ["", "   ", "42", "5w", "1h-30m", "1h+30m", "abc", "--5s", "+", "-", "1hh", "1h30"])
def test_invalid(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)
'''

H1_FILES = {
    "models.py": '''class Order:
    def __init__(self, order_id: str, items=[], coupon_pct: float = 0.0, tax_rate: float = 0.0):
        self.order_id = order_id
        self.items = items
        self.coupon_pct = coupon_pct
        self.tax_rate = tax_rate
''',
    "discounts.py": '''def apply_coupon(subtotal: float, coupon_pct: float) -> float:
    """Apply percentage discount [0, 100] to subtotal. Raise ValueError if out of range."""
    return subtotal * (1 - coupon_pct / 100.0)
''',
    "service.py": '''from models import Order
from discounts import apply_coupon

SPEC = """
OrderBook specification:
1. Order.items must not share mutable state across instances. Validate qty > 0 and unit_price >= 0 and tax_rate >= 0 (else ValueError).
2. Coupon percentage must be in [0, 100] (else ValueError).
3. Total calculation:
   - subtotal = sum(unit_price * qty)
   - discounted = apply_coupon(subtotal, coupon_pct)
   - total = round(discounted * (1 + tax_rate), 2) using Decimal ROUND_HALF_EVEN so 3 items at 0.10 with 0% coupon & 10% tax == 0.33, and 3 items at 19.99 with 15% off & 8.25% tax == 55.18.
4. OrderBook.place(order) stores order and returns float total; raise ValueError if order_id already exists.
5. OrderBook.revenue() returns exact 2-decimal float sum of placed order totals.
"""

class OrderBook:
    def __init__(self):
        self._orders = {}

    def place(self, order: Order) -> float:
        subtotal = sum(p * q for _, p, q in order.items)
        taxed = subtotal * (1 + order.tax_rate)
        total = apply_coupon(taxed, order.coupon_pct)
        self._orders[order.order_id] = total
        return total

    def revenue(self) -> float:
        return sum(self._orders.values())
'''
}

H1_EVAL = '''import pytest
from models import Order
from service import OrderBook

def test_mutable_default_isolated():
    o1 = Order("a")
    o1.items.append(("x", 10.0, 1))
    assert Order("b").items == []

def test_math_and_coupon_before_tax():
    ob = OrderBook()
    assert ob.place(Order("o1", [("sku1", 0.10, 3)], tax_rate=0.10)) == 0.33
    assert ob.place(Order("o2", [("sku2", 19.99, 3)], coupon_pct=15.0, tax_rate=0.0825)) == 55.18
    assert ob.revenue() == 55.51

def test_duplicate_order_rejected():
    ob = OrderBook()
    ob.place(Order("dup", [("a", 5.0, 1)]))
    with pytest.raises(ValueError):
        ob.place(Order("dup", [("a", 5.0, 1)]))

@pytest.mark.parametrize("items,coupon,tax", [
    ([("a", -1.0, 1)], 0, 0), ([("a", 1.0, 0)], 0, 0),
    ([("a", 1.0, -2)], 0, 0), ([("a", 1.0, 1)], -5, 0),
    ([("a", 1.0, 1)], 105, 0), ([("a", 1.0, 1)], 0, -0.05),
])
def test_validation(items, coupon, tax):
    with pytest.raises(ValueError):
        OrderBook().place(Order("bad", items, coupon_pct=coupon, tax_rate=tax))
'''

H2_FILES = {
    "jwt_hs256.py": '''# Implement verify_hs256(token: str, secret: bytes, now: int) -> dict using Python stdlib ONLY.
# Must:
# 1. Parse compact JWS "header.payload.signature" (base64url without '=' padding; reject wrong segment count, invalid base64url chars, non-JSON/non-dict header or payload).
# 2. Enforce header["alg"] == "HS256" strictly (reject "none", "HS512", missing alg, non-string alg).
# 3. Verify HMAC-SHA256 signature using constant-time comparison (`hmac.compare_digest`).
# 4. Enforce temporal claims if present:
#    - `exp`: must be int/float (not bool) and `now < exp` (token is expired when `now >= exp`).
#    - `nbf`: must be int/float (not bool) and `now >= nbf`.
# 5. Return payload dict on success; raise `ValueError` on ANY validation/signature/expiry failure.
'''
}

H2_EVAL = '''import base64, hashlib, hmac, json, pytest
from jwt_hs256 import verify_hs256

SECRET = b"super-secret-key-32-bytes-long!!"

def _b64u(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _make(hdr, pay, secret=SECRET):
    h = _b64u(json.dumps(hdr, separators=(",", ":")).encode())
    p = _b64u(json.dumps(pay, separators=(",", ":")).encode())
    sig = _b64u(hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"

def test_valid_and_claims():
    tok = _make({"alg": "HS256", "typ": "JWT"}, {"sub": "emin", "exp": 2000, "nbf": 1000})
    assert verify_hs256(tok, SECRET, 1000)["sub"] == "emin"
    assert verify_hs256(tok, SECRET, 1999)["sub"] == "emin"

def test_alg_none_and_wrong_alg_rejected():
    h = _b64u(b'{"alg":"none"}')
    p = _b64u(b'{"sub":"admin"}')
    with pytest.raises(ValueError):
        verify_hs256(f"{h}.{p}.", SECRET, 1000)
    with pytest.raises(ValueError):
        verify_hs256(_make({"alg": "HS512"}, {"sub": "x"}), SECRET, 1000)

def test_wrong_secret_and_tampered_payload():
    tok = _make({"alg": "HS256"}, {"sub": "user", "role": "guest"})
    with pytest.raises(ValueError):
        verify_hs256(tok, b"wrong", 1000)
    parts = tok.split(".")
    tampered = _b64u(b'{"sub":"user","role":"admin"}')
    with pytest.raises(ValueError):
        verify_hs256(f"{parts[0]}.{tampered}.{parts[2]}", SECRET, 1000)

def test_exp_and_nbf_boundaries_and_bool_trap():
    tok = _make({"alg": "HS256"}, {"exp": 1000, "nbf": 500})
    with pytest.raises(ValueError):
        verify_hs256(tok, SECRET, 1000)
    with pytest.raises(ValueError):
        verify_hs256(tok, SECRET, 499)
    with pytest.raises(ValueError):
        verify_hs256(_make({"alg": "HS256"}, {"exp": True}), SECRET, 0)

@pytest.mark.parametrize("bad", ["", "a.b", "a.b.c.d", "!!!.@@@.###"])
def test_malformed(bad):
    with pytest.raises(ValueError):
        verify_hs256(bad, SECRET, 1000)
'''

TASKS = {
    "T1_retry_bugfix": {
        "files": T1_FILES, "eval": T1_EVAL,
        "prompt": "Fix the bugs in `retry_util.py` so it satisfies its docstring specification, and verify your fix.",
    },
    "T2_duration_feature": {
        "files": T2_FILES, "eval": T2_EVAL,
        "prompt": "Implement `parse_duration` in `duration.py` according to the comments at the top of the file, and verify it.",
    },
    "H1_financial_multifile": {
        "files": H1_FILES, "eval": H1_EVAL,
        "prompt": "Fix the bugs across `models.py`, `discounts.py`, and `service.py` so everything satisfies `SPEC` in `service.py`, and verify with tests.",
    },
    "H2_jwt_security": {
        "files": H2_FILES, "eval": H2_EVAL,
        "prompt": "Implement `verify_hs256` in `jwt_hs256.py` per the specification comments at the top of the file, and verify it.",
    },
}


def run_process(cmd, cwd, timeout, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
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


def usage_from_session(session_id):
    usage = {"turns": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not session_id:
        return usage
    pattern = os.path.expanduser(f"~/.kimi-code/sessions/**/{session_id}/agents/*/wire.jsonl")
    for wire in glob.glob(pattern, recursive=True):
        with open(wire, errors="ignore") as handle:
            for line in handle:
                if '"usage.record"' not in line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "usage.record":
                    continue
                data = event.get("usage") or {}
                input_tokens = sum(data.get(k, 0) for k in ("inputOther", "inputCacheRead", "inputCacheCreation"))
                output_tokens = data.get("output", 0)
                usage["turns"] += 1
                usage["input_tokens"] += input_tokens
                usage["output_tokens"] += output_tokens
                usage["total_tokens"] += input_tokens + output_tokens
    return usage


def hidden_test(task, work):
    eval_dir = Path(tempfile.mkdtemp(prefix="r5-hidden-"))
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


def run_cell(job, retry_limit=5):
    variant, task_id, repetition, *effort_parts = job
    effort = effort_parts[0] if effort_parts else None
    cid = f"{variant}__{task_id}__r{repetition}"
    if effort:
        cid += f"__{effort}"
    work = OUT / "work" / cid
    task = TASKS[task_id]
    agent_file = OUT / "agents" / f"{variant}.md"
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    body = BASE_SYSTEM_TEMPLATE or "${base_prompt}"
    if "__R5_CWD_LISTING__" in body:
        listing = "\n".join(f"├── {name}" for name in task["files"])
        body = body.replace("__R5_CWD_LISTING__", listing)
    if VARIANTS[variant].strip():
        body += "\n\n" + VARIANTS[variant].strip()
    agent_file.write_text(f"---\nname: r5-{variant.lower().replace('_', '-')}\ndescription: Round 5 controlled prompt variant\n---\n\n{body}\n")
    skills = OUT / "empty_skills"
    skills.mkdir(exist_ok=True)
    cmd = [
        KIMI, "--agent-file", str(agent_file), "--skills-dir", str(skills),
        "--model", MODEL, "--output-format", "stream-json", "-p", task["prompt"],
    ]
    (OUT / "raw").mkdir(exist_ok=True)
    result = None
    for attempt in range(1, retry_limit + 1):
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        for name, content in task["files"].items():
            (work / name).write_text(content)
        started = time.time()
        rc, stdout, stderr = run_process(
            cmd, str(work), 180,
            {"KIMI_MODEL_THINKING_EFFORT": effort} if effort else None,
        )
        elapsed = round(time.time() - started, 2)
        (OUT / "raw" / f"{cid}.attempt{attempt}.stdout.jsonl").write_text(stdout)
        (OUT / "raw" / f"{cid}.attempt{attempt}.stderr.txt").write_text(stderr)
        if rc not in (0, -1) and attempt < retry_limit:
            delay = min(60, 5 * (2 ** (attempt - 1)))
            print(f"{cid} INFRA rc={rc}; retry {attempt + 1}/{retry_limit} after {delay}s", flush=True)
            time.sleep(delay)
            continue
        session_id = ""
        final_text = ""
        tool_calls = 0
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "session.resume_hint":
                session_id = event.get("session_id", "")
            if event.get("role") == "assistant":
                tool_calls += len(event.get("tool_calls") or [])
                if event.get("content"):
                    final_text = event["content"]
        infra_error = rc not in (0, -1)
        if infra_error:
            passed, detail = None, "Infrastructure failure excluded from quality scoring"
        else:
            passed, detail = hidden_test(task, work)
        result = {
            "id": cid, "variant": variant, "task": task_id, "repetition": repetition,
            "model": MODEL, "thinking_effort": effort or "config_default",
            "rc": rc, "passed": passed, "infra_error": infra_error,
            "attempts": attempt, "elapsed_s": elapsed, "tool_calls": tool_calls,
            "final_text": final_text, "code_loc": count_loc(work, list(task["files"])),
            "eval_detail": detail, "stderr": stderr[-1000:], "work_dir": str(work),
            **usage_from_session(session_id),
        }
        break
    with open(OUT / "results.jsonl", "a") as handle:
        handle.write(json.dumps(result) + "\n")
    print(
        f"{cid} pass={result['passed']} rc={result['rc']} tok={result['total_tokens']} "
        f"out={result['output_tokens']} wall={result['elapsed_s']}s loc={result['code_loc']}",
        flush=True,
    )
    return result


def parse_json_text(text):
    stripped = text.strip()
    if "```json" in stripped:
        stripped = stripped.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in stripped:
        stripped = stripped.split("```", 1)[1].split("```", 1)[0].strip()
    return json.loads(stripped)


def judge_task(task_id, results):
    rng = random.Random(SEED + len(task_id))
    shuffled = list(results)
    rng.shuffle(shuffled)
    mapping = {f"CANDIDATE_{chr(65 + i)}": r["id"] for i, r in enumerate(shuffled)}
    bundles = []
    for anon, cid in mapping.items():
        result = next(r for r in results if r["id"] == cid)
        work = Path(result["work_dir"])
        files = []
        for name in TASKS[task_id]["files"]:
            path = work / name
            files.append(f"### {name}\n```python\n{path.read_text(errors='ignore') if path.exists() else '(MISSING)'}\n```")
        bundles.append(
            f"## {anon}\nHidden tests passed: {result['passed']}\n"
            f"Agent response:\n{result['final_text'][:1200]}\n" + "\n".join(files)
        )
    schema = ",\n".join(
        f'"{anon}": {{"correctness_40": int, "robustness_30": int, "craft_20": int, "brevity_10": int, "total_100": int, "reason": string}}'
        for anon in mapping
    )
    prompt = f"""You are a blind code-quality judge. Compare anonymized solutions to the task below. Do not infer or reward model, prompt, or harness identity. Hidden-test outcomes are supplied; inspect every implementation for missed edge cases, security defects, unnecessary complexity, and concision. Score each axis independently.

TASK: {TASKS[task_id]['prompt']}

STARTING FILES:
{json.dumps(TASKS[task_id]['files'], indent=2)}

CANDIDATES:
{''.join(bundles)}

Return STRICT JSON ONLY with this shape:
{{"scores": {{{schema}}}, "winner": "CANDIDATE_...", "summary": "one concise evidence-based sentence"}}"""
    rc, stdout, stderr = run_process([
        "pi", "-p", "--mode", "json", "--no-session", "--no-context-files",
        "--no-extensions", "--no-mcp", "--no-skills", "--no-tools",
        "--provider", "allmodels", "--model", "deepseek/deepseek-v4.1-flash-abliterated",
        "--thinking", "high", "--", prompt,
    ], str(OUT), 240)
    final_text = ""
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn_end":
            texts = [c.get("text", "") for c in event.get("message", {}).get("content", []) if c.get("type") == "text"]
            if texts:
                final_text = "\n".join(texts)
    parsed = None
    try:
        parsed = parse_json_text(final_text)
    except Exception:
        pass
    output = {"task": task_id, "mapping": mapping, "rc": rc, "judgment": parsed, "raw": final_text, "stderr": stderr[-1000:]}
    (OUT / f"blind_{task_id}.json").write_text(json.dumps(output, indent=2))
    print(f"BLIND {task_id} rc={rc} parsed={parsed is not None}", flush=True)
    return output


def aggregate(results, judgments):
    scores = {}
    for judgment in judgments:
        if not judgment["judgment"]:
            continue
        for anon, score in judgment["judgment"].get("scores", {}).items():
            cid = judgment["mapping"].get(anon)
            if cid:
                scores[cid] = score.get("total_100")
    grouped = {}
    for variant in VARIANTS:
        rows = [r for r in results if r["variant"] == variant and not r.get("infra_error")]
        if not rows:
            continue
        passes = sum(r["passed"] for r in rows)
        pass_rate = passes / len(rows)
        token_rows = [r for r in rows if r["total_tokens"] > 0]
        mean_tokens = sum(r["total_tokens"] for r in token_rows) / len(token_rows)
        mean_wall = sum(r["elapsed_s"] for r in rows) / len(rows)
        blind = [scores[r["id"]] for r in rows if scores.get(r["id"]) is not None]
        grouped[variant] = {
            "runs": len(rows), "completed_runs": sum(r["rc"] == 0 for r in rows),
            "timeouts": sum(r["rc"] == -1 for r in rows), "token_runs": len(token_rows),
            "passes": passes, "pass_rate": pass_rate,
            "mean_total_tokens": round(mean_tokens, 1),
            "mean_output_tokens": round(sum(r["output_tokens"] for r in token_rows) / len(token_rows), 1),
            "mean_wall_s": round(mean_wall, 2),
            "mean_code_loc": round(sum(r["code_loc"] for r in rows) / len(rows), 1),
            "mean_tool_calls": round(sum(r["tool_calls"] for r in rows) / len(rows), 1),
            "expected_tokens_per_pass": round(mean_tokens / pass_rate, 1) if pass_rate else None,
            "expected_wall_s_per_pass": round(mean_wall / pass_rate, 2) if pass_rate else None,
            "blind_scores": blind,
            "mean_blind_score": round(sum(blind) / len(blind), 2) if blind else None,
        }
    output = {"model": MODEL, "seed": SEED, "variants": grouped}
    (OUT / "summary.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS))
    parser.add_argument("--tasks", nargs="*", default=list(TASKS))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()
    unknown = set(args.variants) - set(VARIANTS)
    unknown_tasks = set(args.tasks) - set(TASKS)
    if unknown or unknown_tasks:
        raise SystemExit(f"Unknown variants/tasks: {sorted(unknown)} {sorted(unknown_tasks)}")
    selected = {k: v for k, v in VARIANTS.items() if k in args.variants}
    VARIANTS.clear()
    VARIANTS.update(selected)
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(v, t, r) for v in VARIANTS for t in args.tasks for r in range(1, args.repetitions + 1)]
    random.Random(SEED).shuffle(jobs)
    completed = {}
    results_file = OUT / "results.jsonl"
    if results_file.exists():
        for line in results_file.read_text().splitlines():
            old = json.loads(line)
            if old.get("rc") in (0, -1) and not old.get("infra_error"):
                completed[(old["variant"], old["task"], old["repetition"])] = old
    pending = [job for job in jobs if job not in completed]
    print(f"RESUME valid={len(completed)} pending={len(pending)}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        fresh = list(pool.map(run_cell, pending))
    results = [completed[job] for job in jobs if job in completed] + fresh
    with open(OUT / "results_final.jsonl", "w") as handle:
        for result in results:
            handle.write(json.dumps(result) + "\n")
    judgments = []
    if not args.skip_judge:
        for task_id in args.tasks:
            judgments.append(judge_task(task_id, [r for r in results if r["task"] == task_id and not r.get("infra_error")]))
    aggregate(results, judgments)
