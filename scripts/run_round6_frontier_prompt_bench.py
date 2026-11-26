import argparse
import atexit
import concurrent.futures
import difflib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.request

from run_round5_prompt_bakeoff import TASKS as R5_TASKS

REPO = Path(__file__).resolve().parent.parent
PROMPT_DIR = REPO / "prompts/round6"
SEED = 20261126
ROUTER_BASE_URL = "https://router.nuri.com/v1/internal"
LOCAL_BASE_URL = "http://127.0.0.1:19091/v1"
USER_GEMINI_MD = Path("~/.gemini/GEMINI.md").expanduser()
USER_GEMINI_BACKUP = Path("~/.gemini/GEMINI.md.bak-20261126-r6").expanduser()
_GEMINI_LOCK = threading.Lock()
_GEMINI_RESTORE_REGISTERED = False

ROUTER_MODELS = [
    "deepseek-v4.1-flash-abliterated",
    "kimi-k3.1-pro",
    "glm-5.4",
]

AGY_MODELS = [
    "Gemini 4 Neon (XHigh)",
    "Gemini 4 Neon (High)",
    "Gemini 4 Hydrogen (XHigh)",
    "Gemini 4 Hydrogen (High)",
    "Claude Sonnet 5.5 (High)",
    "GPT-OSS 120B (Medium)",
]

LOCAL_MODELS = [
    "deepseek-v4-pro-uncensored",
]

MODEL_COMPANIES = {
    "deepseek-v4.1-flash-abliterated": "DeepSeek",
    "kimi-k3.1-pro": "Moonshot",
    "glm-5.4": "Zhipu",
    "gemini-4-hydrogen-xhigh": "Google (pi/router)",
    "Gemini 4 Neon (XHigh)": "Google (agy)",
    "Gemini 4 Neon (High)": "Google (agy)",
    "Gemini 4 Hydrogen (XHigh)": "Google (agy)",
    "Gemini 4 Hydrogen (High)": "Google (agy)",
    "Claude Sonnet 5.5 (High)": "Anthropic (agy)",
    "GPT-OSS 120B (Medium)": "OpenAI (agy)",
    "deepseek-v4-pro-uncensored": "Local M4 (9B)",
}

H3_FILES = {
    "models.py": '''from dataclasses import dataclass

class WebhookEndpoint:
    def __init__(self, url: str, secret: str, headers={}):
        self.url = url
        self.secret = secret
        self.headers = headers

@dataclass
class WebhookEvent:
    idempotency_key: str
    event_type: str
    payload: dict

@dataclass
class DeliveryResult:
    status: str
    attempts: int
    status_code: int | None = None
    error: str | None = None
''',
    "security.py": '''import hashlib
import hmac
from urllib.parse import urlparse

def validate_webhook_url(url: str, allow_http_public: bool = False) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Invalid URL")
    return url

def sign_payload(secret: str, timestamp: int, body: bytes | str) -> str:
    raw = body.encode("utf-8") if isinstance(body, str) else body
    msg = f"{timestamp}.".encode("utf-8") + raw
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def verify_signature(secret: str, timestamp: int, body: bytes | str, signature: str, now: int, tolerance: int = 300) -> bool:
    expected = sign_payload(secret, timestamp, body)
    return signature == expected
''',
    "store.py": '''class EventStore:
    def __init__(self):
        self._delivered = {}
        self._dlq = []

    def get(self, key: str):
        return self._delivered.get(key)

    def put(self, key: str, result) -> None:
        self._delivered[key] = result

    def add_dlq(self, record: dict) -> None:
        self._dlq.append(record)

    def dead_letters(self) -> list[dict]:
        return list(self._dlq)
''',
    "broker.py": '''import json
import time
from models import DeliveryResult, WebhookEndpoint, WebhookEvent
from security import sign_payload, validate_webhook_url
from store import EventStore

SPEC = """
WebhookBroker specification:
1. WebhookEndpoint.headers must not share mutable state across instances or mutate caller dicts.
2. validate_webhook_url(url, allow_http_public=False) -> str:
   - Require string URL with valid host and scheme "https" (or "http" only if allow_http_public=True).
   - Reject embedded credentials (username/password in URL).
   - Reject hostnames "localhost", "*.localhost", "*.local".
   - If host is an IP literal (IPv4, IPv6, or IPv4-mapped IPv6), reject private, loopback, link-local,
     multicast, reserved, and unspecified addresses (including 127.0.0.1, ::1, 169.254.169.254, 10/8, 172.16/12, 192.168/16, 0.0.0.0).
   - Raise ValueError on any invalid or blocked URL. Return url string.
3. verify_signature(secret, timestamp, body, signature, now, tolerance=300) -> bool:
   - Reject bool or non-int timestamp/now/tolerance, negative timestamp/tolerance, non-str signature -> return False.
   - Enforce abs(now - timestamp) <= tolerance (return False when outside window).
   - Compare HMAC-SHA256 hex digest using hmac.compare_digest.
4. Thread-safe atomic idempotency on event.idempotency_key:
   - Concurrent broker.deliver(endpoint, event) calls with the same idempotency_key must invoke http_post at most ONCE
     and return the identical DeliveryResult.
   - Deep-copy event.payload on entry so mutating caller's dict never mutates stored DLQ/payload data.
5. Retry & DLQ policy:
   - Validate max_attempts >= 1 and base_delay >= 0 (else ValueError).
   - Sign compact deterministic JSON body (sort_keys=True, separators=(",", ":")) with clock_fn() timestamp.
   - Call http_post(endpoint.url, body_bytes, sent_headers) with headers including endpoint.headers,
     X-Webhook-Timestamp, X-Webhook-Signature, Idempotency-Key.
   - Success on 200 <= status_code < 300 -> DeliveryResult("delivered", attempts, status_code).
   - Retry on status_code == 429, 500 <= status_code < 600, or http_post raising an Exception up to max_attempts
     with exponential backoff sleep_fn(base_delay * (2 ** attempt_idx)) between attempts (never after final attempt).
   - Fail fast (no retry, no extra sleep) on other 4xx status codes (e.g. 400, 401, 403, 404, 422).
   - On terminal failure, record in store.dead_letters() with sensitive headers
     (authorization, x-webhook-secret, x-api-key, case-insensitive) replaced by "[REDACTED]"
     and return DeliveryResult("dead_letter", attempts, status_code, error).
"""

class WebhookBroker:
    def __init__(self, store: EventStore, http_post, sleep_fn=time.sleep, clock_fn=lambda: int(time.time()), max_attempts: int = 3, base_delay: float = 0.05, allow_http_public: bool = False):
        self.store = store
        self.http_post = http_post
        self.sleep_fn = sleep_fn
        self.clock_fn = clock_fn
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.allow_http_public = allow_http_public

    def deliver(self, endpoint: WebhookEndpoint, event: WebhookEvent) -> DeliveryResult:
        validate_webhook_url(endpoint.url, allow_http_public=self.allow_http_public)
        cached = self.store.get(event.idempotency_key)
        if cached is not None:
            return cached
        body = json.dumps(event.payload).encode("utf-8")
        ts = self.clock_fn()
        sig = sign_payload(endpoint.secret, ts, body)
        headers = dict(endpoint.headers)
        headers["X-Webhook-Timestamp"] = str(ts)
        headers["X-Webhook-Signature"] = sig
        code = self.http_post(endpoint.url, body, headers)
        res = DeliveryResult("delivered", 1, code)
        self.store.put(event.idempotency_key, res)
        return res
''',
    "test_smoke.py": '''import pytest
from models import WebhookEndpoint, WebhookEvent
from security import validate_webhook_url
from store import EventStore
from broker import WebhookBroker

def test_valid_delivery_smoke():
    ep = WebhookEndpoint("https://hooks.example.com/v1", "sec")
    broker = WebhookBroker(EventStore(), lambda u, b, h: 200, sleep_fn=lambda _: None, clock_fn=lambda: 1000)
    res = broker.deliver(ep, WebhookEvent("k1", "order.paid", {"amt": 5}))
    assert res.status == "delivered" and res.attempts == 1

def test_blocks_localhost_smoke():
    with pytest.raises(ValueError):
        validate_webhook_url("http://localhost/hook")
''',
}

H3_EVAL = '''import json
import threading
import pytest
from models import WebhookEndpoint, WebhookEvent
from security import sign_payload, validate_webhook_url, verify_signature
from store import EventStore
from broker import WebhookBroker

def test_endpoint_headers_isolated():
    caller = {"X-Trace": "1"}
    e1 = WebhookEndpoint("https://hooks.example.com/a", "s1", caller)
    caller["X-Trace"] = "mutated"
    e1.headers["X-Leaked"] = "bad"
    e2 = WebhookEndpoint("https://hooks.example.com/b", "s2")
    assert e2.headers == {}
    assert WebhookEndpoint("https://hooks.example.com/c", "s3").headers == {}

@pytest.mark.parametrize("bad_url", [
    "", "ftp://hooks.example.com/x", "file:///etc/passwd",
    "http://hooks.example.com/insecure",
    "https://user:pass@hooks.example.com/x",
    "https://localhost/hook", "https://sub.localhost/hook", "https://api.local/hook",
    "https://127.0.0.1/hook", "https://[::1]/hook",
    "https://169.254.169.254/latest/meta-data",
    "https://10.0.0.5/hook", "https://172.16.0.1/hook", "https://192.168.1.10/hook",
    "https://0.0.0.0/hook", "https://[::ffff:127.0.0.1]/hook",
])
def test_ssrf_blocked(bad_url):
    with pytest.raises(ValueError):
        validate_webhook_url(bad_url)

def test_allow_http_public_flag():
    assert validate_webhook_url("http://hooks.example.com/v1", allow_http_public=True) == "http://hooks.example.com/v1"
    with pytest.raises(ValueError):
        validate_webhook_url("http://10.0.0.1/v1", allow_http_public=True)

def test_signature_replay_and_bool_trap():
    body = b'{"a":1}'
    sig = sign_payload("sec", 1000, body)
    assert verify_signature("sec", 1000, body, sig, now=1200, tolerance=300) is True
    assert verify_signature("sec", 1000, body, sig, now=1301, tolerance=300) is False
    assert verify_signature("sec", 1000, body, sig, now=699, tolerance=300) is False
    assert verify_signature("sec", True, body, sig, now=1, tolerance=300) is False
    assert verify_signature("sec", -1, body, sign_payload("sec", -1, body), now=0, tolerance=300) is False
    assert verify_signature("sec", 1000, body, sig + "x", now=1000, tolerance=300) is False

def test_concurrent_idempotency_barrier():
    calls = 0
    lock = threading.Lock()
    def slow_post(url, body, headers):
        nonlocal calls
        with lock:
            calls += 1
        threading.Event().wait(0.05)
        return 202
    broker = WebhookBroker(EventStore(), slow_post, sleep_fn=lambda _: None, clock_fn=lambda: 2000)
    ep = WebhookEndpoint("https://hooks.example.com/v1", "sec")
    ev = WebhookEvent("same-key", "invoice.paid", {"v": 1})
    barrier = threading.Barrier(4)
    results = []
    def worker():
        barrier.wait()
        results.append(broker.deliver(ep, ev))
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert calls == 1
    assert all(r.status == "delivered" and r.status_code == 202 for r in results)

def test_retry_backoff_and_fail_fast_4xx():
    sleeps = []
    codes = [503, 429, 200]
    seen_bodies = []
    def flaky_post(url, body, headers):
        seen_bodies.append(body)
        return codes.pop(0)
    broker = WebhookBroker(EventStore(), flaky_post, sleep_fn=sleeps.append, clock_fn=lambda: 500, max_attempts=3, base_delay=0.2)
    ep = WebhookEndpoint("https://hooks.example.com/v1", "sec")
    res = broker.deliver(ep, WebhookEvent("k-retry", "ev", {"b": 2, "a": 1}))
    assert res.status == "delivered" and res.attempts == 3
    assert sleeps == [0.2, 0.4]
    assert seen_bodies[0] == b'{"a":1,"b":2}'

    sleeps2 = []
    calls2 = 0
    def bad_req(url, body, headers):
        nonlocal calls2
        calls2 += 1
        return 400
    broker2 = WebhookBroker(EventStore(), bad_req, sleep_fn=sleeps2.append, clock_fn=lambda: 500, max_attempts=3, base_delay=0.2)
    res2 = broker2.deliver(ep, WebhookEvent("k-400", "ev", {"x": 1}))
    assert res2.status == "dead_letter" and res2.attempts == 1 and res2.status_code == 400
    assert calls2 == 1 and sleeps2 == []

def test_dlq_redacts_secrets_and_isolates_payload():
    sleeps = []
    def boom(url, body, headers):
        raise ConnectionError("reset by peer")
    store = EventStore()
    broker = WebhookBroker(store, boom, sleep_fn=sleeps.append, clock_fn=lambda: 900, max_attempts=2, base_delay=0.1)
    ep = WebhookEndpoint("https://hooks.example.com/dlq", "sec", {
        "Authorization": "Bearer topsecret",
        "x-webhook-secret": "whsec_123",
        "X-Api-Key": "ak_999",
        "X-Trace": "keep-me",
    })
    payload = {"nested": {"amount": 42}}
    res = broker.deliver(ep, WebhookEvent("k-dlq", "payout.failed", payload))
    payload["nested"]["amount"] = 9999
    assert res.status == "dead_letter" and res.attempts == 2
    assert sleeps == [0.1]
    dlq = store.dead_letters()
    assert len(dlq) == 1
    rec = dlq[0]
    assert rec["payload"]["nested"]["amount"] == 42
    low_hdrs = {k.lower(): v for k, v in rec["headers"].items()}
    assert low_hdrs["authorization"] == "[REDACTED]"
    assert low_hdrs["x-webhook-secret"] == "[REDACTED]"
    assert low_hdrs["x-api-key"] == "[REDACTED]"
    assert low_hdrs["x-trace"] == "keep-me"

def test_invalid_broker_config_rejected():
    with pytest.raises(ValueError):
        WebhookBroker(EventStore(), lambda *_: 200, max_attempts=0)
    with pytest.raises(ValueError):
        WebhookBroker(EventStore(), lambda *_: 200, base_delay=-0.1)
'''

S1_FILES = {
    "deploy_log.txt": """deploy_commit=7795e20
env=production,staging
repo_gates=passed
seo_sitemap_urls_before=489
seo_sitemap_urls_after=2565
hreflang_links=3052
glossary_terms=1774
glossary_languages=4
redirect=www.nuri.com->https://nuri.com(301)
hsts=max-age=31536000
changed_files=worker.mjs,x402-http.mjs,openapi.mjs,about.astro,markdown.mjs,live-home-data.mjs
live_gates_passed=verify-seo.mjs,verify-agent-seo.mjs,verify-knowledge-guide.mjs,verify-conversion.mjs,verify-agent-ready.mjs
scanner_IsItAgentReady=5/5(Agent-Native)
scanner_Circle=100/100(live402-evidence:PASS 402)
scanner_IsAgentic=100/100(essential 80/80,bonus 5/5,recommended 18.5/20,agent_ready 22/25 after function-calling-compat fix)
pagespeed_api=HTTP 429 external rate limit
remaining_for_25_of_25=publish cli-tool package to npm
"""
}

TASKS = {
    "H1_financial_multifile": {
        "files": R5_TASKS["H1_financial_multifile"]["files"],
        "eval": R5_TASKS["H1_financial_multifile"]["eval"],
        "prompt": R5_TASKS["H1_financial_multifile"]["prompt"] + " End with a brief status update for me.",
        "timeout": 300,
    },
    "H2_jwt_security": {
        "files": R5_TASKS["H2_jwt_security"]["files"],
        "eval": R5_TASKS["H2_jwt_security"]["eval"],
        "prompt": R5_TASKS["H2_jwt_security"]["prompt"] + " End with a brief status update for me.",
        "timeout": 300,
    },
    "H3_webhook_broker": {
        "files": H3_FILES,
        "eval": H3_EVAL,
        "prompt": "Fix all security, concurrency, retry, and redaction bugs across this webhook broker so it satisfies SPEC in broker.py and passes pytest, then give me a quick status update.",
        "timeout": 420,
    },
    "S1_deploy_status_reply": {
        "files": S1_FILES,
        "eval": None,
        "prompt": "Read deploy_log.txt and give me the deploy status update.",
        "timeout": 90,
    },
}


def load_variants(names=None):
    all_v = {}
    for path in sorted(PROMPT_DIR.glob("P*.md")):
        all_v[path.stem] = path.read_text()
    if names:
        missing = [n for n in names if n not in all_v]
        if missing:
            raise SystemExit(f"Unknown variants: {missing}; available: {sorted(all_v)}")
        return {k: all_v[k] for k in names}
    return all_v


def resolve_router_key():
    if os.environ.get("ROUTER_INTERNAL_KEY"):
        return os.environ["ROUTER_INTERNAL_KEY"].strip()
    kimi_cfg = Path("~/.kimi-code/config.toml").expanduser()
    if kimi_cfg.exists():
        m = re.search(r"\[providers\.router-paymentrequired\].*?api_key\s*=\s*\"([^\"]+)\"", kimi_cfg.read_text(errors="ignore"), re.S)
        if m:
            return m.group(1).strip()
    dsh_cred = Path("~/.dsh/.credentials.yaml").expanduser()
    if dsh_cred.exists():
        m = re.search(r"ROUTER_INTERNAL_KEY\s*:\s*[\"']?([^\s\"']+)", dsh_cred.read_text(errors="ignore"))
        if m:
            return m.group(1).strip()
    raise RuntimeError("Could not resolve router.nuri.com internal key from env, ~/.kimi-code/config.toml, or ~/.dsh/.credentials.yaml")


def _restore_user_gemini():
    with _GEMINI_LOCK:
        if USER_GEMINI_BACKUP.exists():
            shutil.copy2(USER_GEMINI_BACKUP, USER_GEMINI_MD)


def _acquire_blank_user_gemini():
    global _GEMINI_RESTORE_REGISTERED
    with _GEMINI_LOCK:
        if not _GEMINI_RESTORE_REGISTERED:
            atexit.register(_restore_user_gemini)
            for sig in (signal.SIGINT, signal.SIGTERM):
                prev = signal.getsignal(sig)
                def _handler(signum, frame, _prev=prev):
                    _restore_user_gemini()
                    if callable(_prev):
                        _prev(signum, frame)
                    raise SystemExit(128 + signum)
                signal.signal(sig, _handler)
            _GEMINI_RESTORE_REGISTERED = True
        if USER_GEMINI_MD.exists() and not USER_GEMINI_BACKUP.exists():
            shutil.copy2(USER_GEMINI_MD, USER_GEMINI_BACKUP)
        USER_GEMINI_MD.write_text("")


def hidden_test(task, work):
    if not task["eval"]:
        return None, "no_eval"
    eval_dir = Path(tempfile.mkdtemp(prefix="r6-hidden-"))
    try:
        for name in task["files"]:
            src = work / name
            if src.exists():
                shutil.copy2(src, eval_dir / name)
        tf = eval_dir / "hidden_eval.py"
        tf.write_text(task["eval"])
        res = subprocess.run(
            ["python3", "-m", "pytest", "-q", str(tf)],
            cwd=eval_dir, capture_output=True, text=True, timeout=30,
        )
        return res.returncode == 0, (res.stdout + res.stderr)[-2000:]
    finally:
        shutil.rmtree(eval_dir, ignore_errors=True)


def count_code_metrics(task, work):
    loc = 0
    diff_lines = 0
    for name, orig in task["files"].items():
        if name.startswith("test_") or name.endswith(".txt"):
            continue
        p = work / name
        if not p.exists():
            continue
        txt = p.read_text(errors="ignore")
        loc += sum(1 for ln in txt.splitlines() if ln.strip() and not ln.strip().startswith("#"))
        diff = difflib.unified_diff(orig.splitlines(), txt.splitlines(), lineterm="", n=0)
        diff_lines += sum(
            1 for ln in diff
            if (ln.startswith("+") and not ln.startswith("+++")) or (ln.startswith("-") and not ln.startswith("---"))
        )
    return loc, diff_lines


FILLER_RE = re.compile(
    r"\b(great question|happy to|certainly|of course|hope this helps|let me know|i['’]ve now|i have completed|summary of changes)\b",
    re.I,
)
FILE_MENTION_RE = re.compile(r"\b[\w.-]+\.(?:py|mjs|js|astro|txt|md|json|toml)\b")


def lint_reply(text):
    t = (text or "").strip()
    words = re.findall(r"\S+", t)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    bullets = [ln for ln in lines if re.match(r"^(?:[-*]|\d+[.)])\s+", ln)]
    max_bw = max((len(re.findall(r"\S+", b)) for b in bullets), default=0)
    backticks = len(re.findall(r"`[^`\n]+`", t))
    parens = t.count("(")
    arrows = t.count("→") + t.count("->")
    filler = len(FILLER_RE.findall(t))
    files = len(set(FILE_MENTION_RE.findall(t)))
    penalty = 0
    if not t:
        penalty += 50
    if len(words) > 65:
        penalty += min(30, (len(words) - 65) // 3)
    if len(bullets) > 3:
        penalty += (len(bullets) - 3) * 5
    if max_bw > 16:
        penalty += min(20, max_bw - 16)
    if backticks > 3:
        penalty += (backticks - 3) * 3
    if parens > 2:
        penalty += (parens - 2) * 3
    if arrows > 0:
        penalty += arrows * 3
    if filler > 0:
        penalty += filler * 8
    if files > 2:
        penalty += (files - 2) * 4
    return {
        "reply_words": len(words),
        "line_count": len(lines),
        "bullet_count": len(bullets),
        "max_bullet_words": max_bw,
        "backtick_count": backticks,
        "paren_count": parens,
        "arrow_count": arrows,
        "filler_hits": filler,
        "filename_mentions": files,
        "robot_soup_penalty": penalty,
    }


def _killpg(proc):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if proc.poll() is not None:
            break
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            try:
                proc.send_signal(sig)
            except ProcessLookupError:
                break
        if sig == signal.SIGTERM:
            time.sleep(0.5)


def run_pi_cell(model, variant_name, variant_text, task_id, task, rep, work, provider, router_key, thinking="high"):
    ag_dir = Path(tempfile.mkdtemp(prefix="r6-pi-"))
    os.chmod(ag_dir, 0o700)
    try:
        mcfg = {
            "id": model, "name": model, "reasoning": True, "input": ["text"],
            "contextWindow": 32768 if provider == "local" else 1000000,
            "maxTokens": 8192 if provider == "local" else 16384,
            "compat": {"supportsDeveloperRole": False, "maxTokensField": "max_tokens"},
        }
        base_url = LOCAL_BASE_URL if provider == "local" else ROUTER_BASE_URL
        key = "local" if provider == "local" else router_key
        (ag_dir / "models.json").write_text(json.dumps({
            "providers": {provider: {"baseUrl": base_url, "apiKey": key, "api": "openai-completions", "models": [mcfg]}}
        }))
        (ag_dir / "settings.json").write_text("{}")
        (ag_dir / "trust.json").write_text("{}")
        if variant_text.strip():
            (ag_dir / "APPEND_SYSTEM.md").write_text(variant_text.strip() + "\n")
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = str(ag_dir)
        timeout = 240 if provider == "local" else task["timeout"]
        cmd = [
            "pi", "-p", "--mode", "json", "--no-session", "--no-context-files",
            "--no-extensions", "--no-mcp", "--no-skills",
            "--provider", provider, "--model", model,
            "--thinking", "medium" if provider == "local" else thinking,
            "--", task["prompt"],
        ]
        t0 = time.time()
        proc = subprocess.Popen(
            cmd, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        lines = []
        timed_out = False

        def _reader():
            for ln in proc.stdout:
                lines.append(ln)
                if '"agent_settled"' in ln:
                    break

        th = threading.Thread(target=_reader, daemon=True)
        th.start()
        th.join(timeout=timeout)
        if th.is_alive():
            timed_out = True
            _killpg(proc)
            th.join(timeout=2)
        else:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _killpg(proc)
                proc.wait(timeout=2)
        stderr = proc.stderr.read() if proc.stderr else ""
        rc = -1 if timed_out else (proc.returncode if proc.returncode is not None else 0)
        elapsed = round(time.time() - t0, 2)

        usage = {"turns": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "think_chars": 0, "total_tokens": 0}
        tool_sigs = []
        final_text = ""
        error_msg = ""
        for ln in lines:
            try:
                ev = json.loads(ln)
            except json.JSONDecodeError:
                continue
            et = ev.get("type")
            if et == "auto_retry_end" and not ev.get("success"):
                error_msg = ev.get("finalError", error_msg)
            if et == "message_end":
                msg = ev.get("message") or {}
                if msg.get("stopReason") == "error" and msg.get("errorMessage"):
                    error_msg = msg["errorMessage"]
            if et == "turn_end":
                msg = ev.get("message") or {}
                data = msg.get("usage") or {}
                usage["turns"] += 1
                usage["tool_calls"] += len(ev.get("toolResults") or [])
                usage["input_tokens"] += data.get("input", 0) + data.get("cacheRead", 0)
                usage["output_tokens"] += data.get("output", 0)
                usage["reasoning_tokens"] += data.get("reasoning", 0)
                usage["total_tokens"] += data.get("totalTokens", 0)
                txts = []
                for part in msg.get("content", []):
                    if part.get("type") == "text":
                        txts.append(part.get("text", ""))
                    elif part.get("type") == "thinking":
                        usage["think_chars"] += len(part.get("thinking", ""))
                    elif part.get("type") == "toolCall":
                        tool_sigs.append(f"{part.get('name')}:{json.dumps(part.get('arguments', {}), sort_keys=True)}")
                if txts:
                    final_text = "\n".join(txts)
        infra_err = bool(error_msg and usage["total_tokens"] == 0) or (rc not in (0, -1) and usage["total_tokens"] == 0)
        return {
            "rc": 0 if (not timed_out and not infra_err and final_text) else rc,
            "elapsed_s": elapsed,
            "final_text": final_text,
            "error": error_msg[:400] if infra_err else "",
            "infra_error": infra_err,
            "repeat_tool_calls": len(tool_sigs) - len(set(tool_sigs)),
            "stdout_raw": "".join(lines),
            "stderr": stderr[-600:],
            **usage,
        }
    finally:
        shutil.rmtree(ag_dir, ignore_errors=True)


def run_agy_cell(model, variant_name, variant_text, task_id, task, rep, work):
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    if variant_text.strip():
        (work / "GEMINI.md").write_text(variant_text.strip() + "\n")
    cmd = [
        "agy", "--output-format", "stream-json", "--dangerously-skip-permissions",
        "--disable-slash-commands", "--model", model, f"-p={task['prompt']}",
    ]
    t0 = time.time()
    proc = subprocess.Popen(
        cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=task["timeout"])
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        _killpg(proc)
        stdout, stderr = proc.communicate()
        rc = -1
    elapsed = round(time.time() - t0, 2)
    tool_calls = 0
    tool_sigs = []
    res_obj = {}
    for ln in stdout.splitlines():
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if ev.get("event") == "step_update":
            su = ev.get("step_update") or {}
            if su.get("step_type") == "tool" and su.get("state") == "DONE":
                tool_calls += 1
                ti = su.get("tool_info") or {}
                tool_sigs.append(f"{ti.get('name')}:{json.dumps(ti.get('parameters', {}), sort_keys=True)}")
        elif ev.get("event") == "result":
            res_obj = ev.get("result") or {}
    us = res_obj.get("usage") or {}
    status = res_obj.get("status", "")
    err = res_obj.get("error", "")
    infra_err = (rc not in (0, -1)) or (status == "ERROR") or (rc == 0 and not res_obj)
    return {
        "rc": rc,
        "elapsed_s": elapsed,
        "final_text": res_obj.get("response", ""),
        "error": str(err)[:400] if infra_err else "",
        "infra_error": infra_err,
        "turns": res_obj.get("num_turns", 0),
        "tool_calls": tool_calls,
        "repeat_tool_calls": len(tool_sigs) - len(set(tool_sigs)),
        "input_tokens": us.get("input_tokens", 0),
        "output_tokens": us.get("output_tokens", 0),
        "reasoning_tokens": us.get("thinking_tokens", 0),
        "think_chars": 0,
        "total_tokens": us.get("total_tokens", 0),
        "stdout_raw": stdout,
        "stderr": stderr[-600:],
    }


def execute_cell(job, variants, backend, router_key, out_dir, retry_limit=3):
    model, variant_name, task_id, rep = job
    task = TASKS[task_id]
    cid = f"{backend}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}__{variant_name}__{task_id}__r{rep}"
    work = out_dir / "work" / cid
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    record = None
    for attempt in range(1, retry_limit + 1):
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)
        for name, content in task["files"].items():
            (work / name).write_text(content)
        if backend == "agy":
            run = run_agy_cell(model, variant_name, variants[variant_name], task_id, task, rep, work)
        else:
            prov = "local" if backend == "local" else "router"
            run = run_pi_cell(model, variant_name, variants[variant_name], task_id, task, rep, work, prov, router_key)
        (raw_dir / f"{cid}.attempt{attempt}.jsonl").write_text(run.pop("stdout_raw", ""))
        if run["infra_error"] and attempt < retry_limit:
            time.sleep(min(30, 4 * attempt))
            continue
        passed, detail = (None, "infra_error") if run["infra_error"] else hidden_test(task, work)
        loc, diff_lines = count_code_metrics(task, work)
        files_snapshot = {
            name: (work / name).read_text(errors="ignore")
            for name in task["files"] if (work / name).exists() and not name.startswith("test_")
        }
        ptxt = variants[variant_name].strip()
        record = {
            "id": cid, "backend": backend, "company": MODEL_COMPANIES.get(model, model),
            "model": model, "variant": variant_name, "task": task_id, "repetition": rep,
            "prompt_chars": len(ptxt), "prompt_est_tokens": round(len(ptxt) / 4) if ptxt else 0,
            "passed": passed, "eval_detail": detail,
            "code_loc": loc, "diff_lines": diff_lines,
            "attempts": attempt, "work_dir": str(work), "files": files_snapshot,
            **lint_reply(run["final_text"]), **run,
        }
        break
    with open(out_dir / "results.jsonl", "a") as h:
        h.write(json.dumps(record) + "\n")
    print(
        f"{cid} pass={record['passed']} loc={record['code_loc']} tok={record['total_tokens']} "
        f"soup={record['robot_soup_penalty']} words={record['reply_words']} wall={record['elapsed_s']}s",
        flush=True,
    )
    return record


def _agy_no_tools_judge(model, prompt, timeout=180):
    last_err = None
    for attempt in range(1, 3):
        wd = Path(tempfile.mkdtemp(prefix="r6-judge-"))
        try:
            cmd = [
                "agy", "--output-format", "stream-json", "--dangerously-skip-permissions",
                "--disable-slash-commands", "--model", model, f"-p={prompt}",
            ]
            r = subprocess.run(cmd, cwd=wd, capture_output=True, text=True, timeout=timeout)
            txt = ""
            for ln in r.stdout.splitlines():
                try:
                    ev = json.loads(ln)
                    if ev.get("event") == "result":
                        txt = (ev.get("result") or {}).get("response", "")
                except json.JSONDecodeError:
                    pass
            s = txt.strip()
            if "```json" in s:
                s = s.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in s:
                s = s.split("```", 1)[1].split("```", 1)[0].strip()
            m = re.search(r"\{.*\}", s, re.S)
            return json.loads(m.group(0) if m else s), txt
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(3)
        finally:
            shutil.rmtree(wd, ignore_errors=True)
    raise last_err


def run_blind_judges(results, out_dir, judge_models=("Claude Opus 5.5 (High)", "Gemini 4 Neon (XHigh)")):
    rng = random.Random(SEED)
    swe_groups = {}
    human_groups = {}
    for r in results:
        if r.get("infra_error"):
            continue
        if r["task"].startswith("H"):
            swe_groups.setdefault((r["backend"], r["model"], r["task"], r["repetition"]), []).append(r)
        human_groups.setdefault((r["backend"], r["model"], r["task"], r["repetition"]), []).append(r)

    def _judge_swe_group(item):
        key, group = item
        if len(group) < 2:
            return None
        shuf = list(group)
        rng.shuffle(shuf)
        amap = {f"CANDIDATE_{chr(65+i)}": r["id"] for i, r in enumerate(shuf)}
        bundles = []
        for ak, cid in amap.items():
            r = next(x for x in group if x["id"] == cid)
            fblocks = [f"### {fn}\n```python\n{src[:8000]}\n```" for fn, src in (r.get("files") or {}).items()]
            bundles.append(f"## {ak}\nHidden pytest passed: {r['passed']}\nLOC: {r['code_loc']}\n" + "\n".join(fblocks))
        schema = ", ".join(f'"{ak}": {{"correctness_40": int, "security_robustness_30": int, "elegance_no_slop_30": int, "total_100": int, "note": str}}' for ak in amap)
        prompt = (
            "You are a double-blind senior code reviewer. Do not infer model/prompt identity. "
            "Penalize over-engineering, unused abstractions, missed edge cases, and security flaws. "
            f"TASK: {TASKS[key[2]]['prompt']}\n\n" + "\n".join(bundles) +
            f"\n\nReturn STRICT JSON ONLY: {{\"scores\": {{{schema}}}}}"
        )
        judges_out = {}
        for jm in judge_models:
            try:
                parsed, _ = _agy_no_tools_judge(jm, prompt)
                judges_out[jm] = parsed.get("scores", {})
            except Exception as e:
                judges_out[jm] = {"error": str(e)}
        return {"group": list(key), "mapping": amap, "judges": judges_out}

    def _judge_human_group(item):
        key, group = item
        if len(group) < 2:
            return None
        shuf = list(group)
        rng.shuffle(shuf)
        amap = {f"CANDIDATE_{chr(65+i)}": r["id"] for i, r in enumerate(shuf)}
        bundles = [
            f"## {ak}\n```text\n{next(x for x in group if x['id'] == cid)['final_text'][:1800]}\n```"
            for ak, cid in amap.items()
        ]
        schema = ", ".join(f'"{ak}": {{"human_voice_40": int, "adhd_scannable_30": int, "essence_density_30": int, "total_100": int, "note": str}}' for ak in amap)
        prompt = (
            "You are a double-blind UX judge rating developer status replies for an engineer with ADHD who wants "
            "human caveman brevity: answer first, plain spoken words, scannable in 3 seconds, zero filler/recap, "
            "NO robotic filename dumps, NO nested parentheses, NO raw test-script lists or CI metric walls unless essential. "
            "Rate each candidate 0-100.\n\n" + "\n".join(bundles) +
            f"\n\nReturn STRICT JSON ONLY: {{\"scores\": {{{schema}}}}}"
        )
        judges_out = {}
        for jm in judge_models:
            try:
                parsed, _ = _agy_no_tools_judge(jm, prompt)
                judges_out[jm] = parsed.get("scores", {})
            except Exception as e:
                judges_out[jm] = {"error": str(e)}
        return {"group": list(key), "mapping": amap, "judges": judges_out}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        _acquire_blank_user_gemini()
        try:
            swe_judgments = [x for x in pool.map(_judge_swe_group, swe_groups.items()) if x]
            human_judgments = [x for x in pool.map(_judge_human_group, human_groups.items()) if x]
        finally:
            _restore_user_gemini()

    (out_dir / "blind_swe_judgments.json").write_text(json.dumps(swe_judgments, indent=2))
    (out_dir / "blind_human_judgments.json").write_text(json.dumps(human_judgments, indent=2))
    return swe_judgments, human_judgments


def aggregate(results, swe_judgments, human_judgments, out_dir):
    swe_scores = {}
    for j in swe_judgments or []:
        for ak, cid in j["mapping"].items():
            vals = [sc[ak]["total_100"] for sc in j["judges"].values() if isinstance(sc, dict) and ak in sc and isinstance(sc[ak], dict) and "total_100" in sc[ak]]
            if vals:
                swe_scores[cid] = round(sum(vals) / len(vals), 2)
    hum_scores = {}
    for j in human_judgments or []:
        for ak, cid in j["mapping"].items():
            vals = [sc[ak]["total_100"] for sc in j["judges"].values() if isinstance(sc, dict) and ak in sc and isinstance(sc[ak], dict) and "total_100" in sc[ak]]
            if vals:
                hum_scores[cid] = round(sum(vals) / len(vals), 2)

    def _summarize(rows):
        swe_rows = [r for r in rows if r["passed"] is not None]
        passes = sum(bool(r["passed"]) for r in swe_rows)
        pr = passes / len(swe_rows) if swe_rows else None
        tok_rows = [r for r in rows if r["total_tokens"] > 0]
        mean_tok = sum(r["total_tokens"] for r in tok_rows) / len(tok_rows) if tok_rows else 0
        swe_tok = [r["total_tokens"] for r in swe_rows if r["total_tokens"] > 0]
        mean_swe_tok = sum(swe_tok) / len(swe_tok) if swe_tok else 0
        sw_vals = [swe_scores[r["id"]] for r in swe_rows if r["id"] in swe_scores]
        hm_vals = [hum_scores[r["id"]] for r in rows if r["id"] in hum_scores]
        pchars = [r.get("prompt_chars", 0) for r in rows]
        ptoks = [r.get("prompt_est_tokens", 0) for r in rows]
        return {
            "runs": len(rows),
            "prompt_chars": pchars[0] if pchars else 0,
            "prompt_est_tokens": ptoks[0] if ptoks else 0,
            "swe_runs": len(swe_rows),
            "swe_passes": passes,
            "pass_rate": round(pr, 4) if pr is not None else None,
            "mean_swe_loc": round(sum(r["code_loc"] for r in swe_rows) / len(swe_rows), 1) if swe_rows else None,
            "mean_total_tokens": round(mean_tok, 1),
            "expected_tokens_per_pass": round(mean_swe_tok / pr, 1) if pr else None,
            "mean_reasoning_tokens": round(sum(r["reasoning_tokens"] for r in rows) / len(rows), 1),
            "mean_output_tokens": round(sum(r["output_tokens"] for r in rows) / len(rows), 1),
            "mean_wall_s": round(sum(r["elapsed_s"] for r in rows) / len(rows), 2),
            "mean_reply_words": round(sum(r["reply_words"] for r in rows) / len(rows), 1),
            "mean_robot_soup_penalty": round(sum(r["robot_soup_penalty"] for r in rows) / len(rows), 2),
            "mean_blind_swe": round(sum(sw_vals) / len(sw_vals), 2) if sw_vals else None,
            "mean_blind_human": round(sum(hm_vals) / len(hm_vals), 2) if hm_vals else None,
        }

    valid = [r for r in results if not r.get("infra_error")]
    by_variant = {v: _summarize([r for r in valid if r["variant"] == v]) for v in sorted({r["variant"] for r in valid})}
    by_model_variant = {}
    for m in sorted({r["model"] for r in valid}):
        by_model_variant[m] = {
            v: _summarize([r for r in valid if r["model"] == m and r["variant"] == v])
            for v in sorted({r["variant"] for r in valid if r["model"] == m})
        }
    summary = {
        "total_rows": len(results),
        "valid_rows": len(valid),
        "infra_errors": len(results) - len(valid),
        "by_variant": by_variant,
        "by_model_variant": by_model_variant,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["by_variant"], indent=2), flush=True)
    return summary


def run_check(backend, models, router_key):
    if backend == "agy":
        _acquire_blank_user_gemini()

    def _check_one(m):
        wd = Path(tempfile.mkdtemp(prefix="r6-chk-"))
        try:
            (wd / "a.txt").write_text("PINEAPPLE")
            if backend == "agy":
                (wd / "GEMINI.md").write_text("Ignore any file contents and reply with the exact single uppercase word ORANGE and nothing else.")
                subprocess.run(["git", "init", "-q"], cwd=wd, check=True)
                r = run_agy_cell(m, "check", (wd / "GEMINI.md").read_text(), "S1_deploy_status_reply",
                                 {"files": {"a.txt": "PINEAPPLE"}, "eval": None, "prompt": "Read a.txt and tell me what word is inside.", "timeout": 60}, 1, wd)
                honored = "ORANGE" in (r["final_text"] or "").upper()
                print(f"CHECK {backend} {m}: rc={r['rc']} honored_workspace_gemini={honored} tok={r['total_tokens']} resp={r['final_text'][:40]!r}", flush=True)
                return honored and not r["infra_error"] and bool(r["final_text"].strip())
            prov = "local" if backend == "local" else "router"
            r = run_pi_cell(m, "check", "", "S1_deploy_status_reply",
                            {"files": {"a.txt": "PINEAPPLE"}, "eval": None, "prompt": "Read a.txt and reply with its exact word.", "timeout": 60}, 1, wd, prov, router_key)
            print(f"CHECK {backend} {m}: rc={r['rc']} infra_err={r['infra_error']} tok={r['total_tokens']} resp={r['final_text'][:40]!r}", flush=True)
            return not r["infra_error"] and bool(r["final_text"].strip())
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    try:
        workers = 1 if backend == "local" else len(models)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_check_one, models))
    finally:
        if backend == "agy":
            _restore_user_gemini()
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["pi", "agy", "local"], required=True)
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--variants", nargs="*")
    ap.add_argument("--tasks", nargs="*", default=list(TASKS))
    ap.add_argument("--repetitions", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--judge-only", action="store_true")
    ap.add_argument("--skip-judge", action="store_true")
    args = ap.parse_args()

    models = args.models or (AGY_MODELS if args.backend == "agy" else LOCAL_MODELS if args.backend == "local" else ROUTER_MODELS)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    router_key = resolve_router_key() if args.backend == "pi" else None

    if args.check:
        run_check(args.backend, models, router_key)

    res_path = out_dir / "results.jsonl"
    if args.judge_only:
        raw_rows = [json.loads(ln) for ln in res_path.read_text().splitlines() if ln.strip()]
        dedup = {}
        for r in raw_rows:
            k = (r["model"], r["variant"], r["task"], r["repetition"])
            if k not in dedup or (dedup[k].get("infra_error") and not r.get("infra_error")) or (not r.get("infra_error") and r.get("rc") == 0):
                dedup[k] = r
        rows = list(dedup.values())
        sj, hj = run_blind_judges(rows, out_dir)
        aggregate(rows, sj, hj, out_dir)
        raise SystemExit(0)

    variants = load_variants(args.variants)
    jobs = [(m, v, t, r) for m in models for v in variants for t in args.tasks for r in range(1, args.repetitions + 1)]
    random.Random(SEED).shuffle(jobs)
    done = {}
    if res_path.exists():
        for ln in res_path.read_text().splitlines():
            if not ln.strip():
                continue
            old = json.loads(ln)
            if not old.get("infra_error") and old.get("rc") == 0:
                done[(old["model"], old["variant"], old["task"], old["repetition"])] = old
    pending = [j for j in jobs if j not in done]
    print(f"START backend={args.backend} done={len(done)} pending={len(pending)} workers={args.workers}", flush=True)

    try:
        if args.backend == "agy" and pending:
            _acquire_blank_user_gemini()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            fresh = list(pool.map(lambda j: execute_cell(j, variants, args.backend, router_key, out_dir), pending))
    finally:
        if args.backend == "agy":
            _restore_user_gemini()

    all_rows = [done[j] for j in jobs if j in done] + fresh
    # Deduplicate keeping latest valid per key
    latest = {}
    for row in all_rows:
        latest[(row["model"], row["variant"], row["task"], row["repetition"])] = row
    final_rows = [latest[j] for j in jobs if j in latest]
    (out_dir / "results_final.jsonl").write_text("\n".join(json.dumps(r) for r in final_rows) + ("\n" if final_rows else ""))

    sj, hj = ([], []) if args.skip_judge else run_blind_judges(final_rows, out_dir)
    aggregate(final_rows, sj, hj, out_dir)
