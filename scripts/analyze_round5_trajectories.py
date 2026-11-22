import glob
import json
import os
from pathlib import Path
import re

R5 = Path("/private/tmp/bench_clean")
PROMPT = R5 / "r5_prompt_bakeoff"
MODEL = R5 / "r5_model_bakeoff"
OUT = R5 / "trajectory_analysis.json"

PATTERNS = {
    "reinterpretation": [
        "need understand", "unclear", "ambiguous", "interpret", "presumably",
        "what does", "not sure", "could mean", "perhaps",
    ],
    "test_hunting": ["hidden test", "tests likely", "locate parent", "find .."],
    "brevity_negotiation": [
        "minimum", "minimal", "fewest", "caveman", "tldr", "no broad", "repeat reads",
    ],
    "useful_correctness": [
        "security", "validate", "signature", "boundary", "decimal", "round_half",
        "constant-time", "idempot", "regression",
    ],
}


def pattern_counts(text):
    low = text.lower()
    return {name: sum(low.count(term) for term in terms) for name, terms in PATTERNS.items()}


def wire_for(raw_path):
    session_id = None
    for line in raw_path.read_text(errors="ignore").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "session.resume_hint":
            session_id = event.get("session_id")
    if not session_id:
        return None
    matches = glob.glob(os.path.expanduser(f"~/.kimi-code/sessions/**/{session_id}/agents/main/wire.jsonl"), recursive=True)
    return Path(matches[0]) if matches else None


def latest_raw(cid):
    candidates = sorted(PROMPT.glob(f"raw/{cid}.attempt*.stdout.jsonl"))
    if candidates:
        return candidates[-1]
    legacy = PROMPT / "raw" / f"{cid}.stdout.jsonl"
    return legacy if legacy.exists() else None


def analyze_kimi():
    rows = [json.loads(line) for line in (PROMPT / "results_final.jsonl").read_text().splitlines()]
    output = []
    for row in rows:
        raw = latest_raw(row["id"])
        if not raw:
            continue
        wire = wire_for(raw)
        if not wire:
            continue
        thinks = []
        tool_signatures = []
        parent_searches = 0
        test_calls = 0
        decode_ms = 0
        request_efforts = set()
        for line in wire.read_text(errors="ignore").splitlines():
            event = json.loads(line)
            if event.get("type") == "llm.request":
                request_efforts.add(event.get("thinkingEffort"))
            if event.get("type") != "context.append_loop_event":
                continue
            loop = event.get("event") or {}
            kind = loop.get("type")
            if kind == "content.part":
                part = loop.get("part") or {}
                if part.get("type") == "think":
                    thinks.append(part.get("think", ""))
            elif kind == "tool.call":
                args = loop.get("args")
                if not isinstance(args, str):
                    args = json.dumps(args, sort_keys=True)
                tool_signatures.append(f"{loop.get('name')}:{args}")
                if re.search(r"\b(find|grep|ls|cat)\s+[^;]*\.\.", args):
                    parent_searches += 1
                if "pytest" in args or "node --test" in args:
                    test_calls += 1
            elif kind == "step.end":
                decode_ms += loop.get("llmServerDecodeMs") or 0
        thought = "\n".join(thinks)
        output.append({
            "id": row["id"], "variant": row["variant"], "task": row["task"],
            "passed": row["passed"], "rc": row["rc"], "thinking_effort": sorted(e for e in request_efforts if e),
            "think_events": len(thinks), "think_chars": len(thought),
            "tool_calls": len(tool_signatures),
            "repeat_tool_calls": len(tool_signatures) - len(set(tool_signatures)),
            "parent_searches": parent_searches, "test_calls": test_calls,
            "llm_server_decode_ms": decode_ms,
            **pattern_counts(thought),
        })
    return output


def analyze_deepseek():
    output = []
    for raw in sorted(MODEL.glob("raw/*.stdout.jsonl")):
        thinks = []
        reasoning_tokens = 0
        tool_signatures = []
        tool_errors = 0
        parent_searches = 0
        test_calls = 0
        decode_ms = 0
        seen_turns = set()
        for line in raw.read_text(errors="ignore").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "message_end":
                message = event.get("message") or {}
                if message.get("role") != "assistant":
                    continue
                data = message.get("usage") or {}
                reasoning_tokens += data.get("reasoning", 0)
                decode_ms += message.get("durationMs") or 0
                for part in message.get("content", []):
                    if part.get("type") == "thinking":
                        thinks.append(part.get("thinking", ""))
                    elif part.get("type") == "toolCall":
                        args = json.dumps(part.get("arguments", {}), sort_keys=True)
                        tool_signatures.append(f"{part.get('name')}:{args}")
                        if re.search(r"\b(find|grep|ls|cat)\s+[^;]*\.\.", args):
                            parent_searches += 1
                        if "pytest" in args or "node --test" in args:
                            test_calls += 1
            elif kind == "turn_end":
                for result in event.get("toolResults") or []:
                    if result.get("isError"):
                        tool_errors += 1
        thought = "\n".join(thinks)
        output.append({
            "id": raw.name.split(".stdout.jsonl")[0], "model": "deepseek-v4.1-flash-abliterated",
            "think_events": len(thinks), "think_chars": len(thought),
            "reasoning_tokens": reasoning_tokens, "tool_calls": len(tool_signatures),
            "repeat_tool_calls": len(tool_signatures) - len(set(tool_signatures)),
            "parent_searches": parent_searches, "test_calls": test_calls,
            "tool_errors": tool_errors, "decode_ms": decode_ms,
            **pattern_counts(thought),
        })
    return output


def summarize(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    summary = {}
    metrics = [
        "think_events", "think_chars", "reasoning_tokens", "tool_calls",
        "repeat_tool_calls", "parent_searches", "test_calls", "tool_errors",
        *PATTERNS,
    ]
    for name, items in grouped.items():
        summary[name] = {
            "runs": len(items),
            **{metric: sum(item.get(metric, 0) for item in items) for metric in metrics},
            **{f"mean_{metric}": round(sum(item.get(metric, 0) for item in items) / len(items), 2) for metric in metrics},
        }
    return summary


if __name__ == "__main__":
    kimi = analyze_kimi()
    deepseek = analyze_deepseek()
    output = {
        "note": "Pattern counts are trajectory-review signals, not proof that reasoning was wasted. Useful correctness reasoning is reported separately.",
        "kimi_summary": summarize(kimi, "variant"),
        "deepseek_summary": summarize(deepseek, "model"),
        "kimi_runs": kimi,
        "deepseek_runs": deepseek,
    }
    OUT.write_text(json.dumps(output, indent=2))
    print(json.dumps({"kimi_summary": output["kimi_summary"], "deepseek_summary": output["deepseek_summary"]}, indent=2))
