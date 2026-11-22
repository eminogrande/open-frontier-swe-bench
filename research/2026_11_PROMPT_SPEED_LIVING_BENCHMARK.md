# Living Prompt, Model-Speed & Reliability Benchmark

**Status:** active. V3 is the published measured baseline. V4a is the user-selected **experimental default**, not yet a measured replacement winner. Update this report and [`CHANGELOG.md`](../CHANGELOG.md) together when a measured round lands.

## Experimental V4a default

The current experimental prompt is [`prompts/V4a_tldr_caveman.md`](../prompts/V4a_tldr_caveman.md):

```text
CAVEMAN + TLDR + ADHD MODE.
TLDR answer first. Max 3 fragments. Zero filler/recap.
Code like caveman: reuse first; min LOC, files, tools, deps; no broad/repeat reads; quiet flags. Keep exact syntax, negations, tests, security, requested format.
```

Global Kimi activation is deliberately deferred until the current controlled run finishes because `$KIMI_CODE_HOME/AGENTS.md` would otherwise be injected into every prompt arm and invalidate the comparison. Activation will use additive `AGENTS.md`, not a V4a-only `SYSTEM.md` override.

The next candidate, [`V4c adaptive effort`](../prompts/V4c_adaptive_effort.md), preserves the same minimalism but explicitly permits deeper reasoning and iteration when blocked, uncertain, or failing tests. Kimi `low`/`high`/`max` reasoning will be compared separately so prompt text and thinking effort are not confounded.

This is the GitHub-native continuation of the original [agent-prompt-brevity-bench](https://github.com/eminogrande/agent-prompt-brevity-bench) study. HackMD is a historical snapshot, not the canonical source for new findings.

## Current published baseline

The published prompt is [`prompts/V3_caveman_adhd_winner.md`](../prompts/V3_caveman_adhd_winner.md), byte-identical to the V3 winner in `agent-prompt-brevity-bench`:

```text
CAVEMAN + ADHD MODE. Active until "stop adhd mode".
Fewest words possible. No fixed word count. Max 3 bullets/steps. Answer first. Short fragments OK. No filler, recaps or tangents. Explain only when asked; obey requested format.
Code like caveman: reuse first. Minimum code, files, tools, dependencies, abstractions. No broad reads. Keep correctness, exact syntax, negations, tests and security.
Tool output: quiet flags; needed lines/failures only. Reuse commands; no repeated reads.
```

Original Pi evidence across small and medium tasks: V3 retained the measured pass rate while reducing total tokens by 30–50%. Those results do not establish reliability on long-horizon brownfield tasks or inside Kimi Code.

## Is V3 active in every Kimi Code session?

No, not by default. The verified local Kimi Code configuration has no `$KIMI_CODE_HOME/AGENTS.md`, `$KIMI_CODE_HOME/SYSTEM.md`, or overriding default main-agent file. `merge_all_available_skills = true` exposes the Skill catalog; it does not inject V3 into every prompt.

Pi does have V3 in its global `APPEND_SYSTEM.md`. The Open Frontier benchmark injects V3 explicitly per run, so its published results do not depend on global Kimi configuration.

For a future global Kimi rollout, prefer `$KIMI_CODE_HOME/AGENTS.md` for additive instructions. `$KIMI_CODE_HOME/SYSTEM.md` replaces the built-in main-agent system prompt and should not contain only V3. See the official [Kimi agent documentation](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/agents.html).

## Arkade replication: what changed our interpretation

The earlier Round 3 solo Kimi Code 2.5.2 + `k3.1-pro-highspeed` run used V3 and passed **7/7 gates**, scored **87/100** blind, and finished in **483s**.

Four fresh V3 solo attempts on the same Arkade task all reached the **600s timeout** before completion:

| Attempt | Execution | Gates at timeout | Added LOC at timeout |
|---|---|---:|---:|
| 1 | 3 concurrent | 1/7 | 0 |
| 2 | 3 concurrent | 3/7 | 338 |
| 3 | 3 concurrent | 4/7 | 328 |
| 4 | uncontended | 3/7 | 364 |

These are incomplete patches, not blind-scored submissions. Token telemetry was unavailable after the timeouts. The correct conclusion is that the earlier 7/7 result was not reproduced reliably under the current setup—not that V3 conclusively caused a regression. A clean prompt-effect claim requires interleaved stock-versus-V3 repetitions under the same current conditions.

This agrees with the independent [Harness Leaderboard](https://huggingface.co/spaces/joelniklaus/harness-leaderboard): re-running the same harness flipped 24.2% of tasks, while swapping harnesses flipped 27.0%. Single-run rankings are therefore insufficient for prompt or harness selection.

## Round 5 prompt study

Runner: [`scripts/run_round5_prompt_bakeoff.py`](../scripts/run_round5_prompt_bakeoff.py).

- **Prompt arms:** stock base, V3, [`V4a TLDR-Caveman`](../prompts/V4a_tldr_caveman.md), and [`V4b TLDR + thinking budget`](../prompts/V4b_tldr_think_budget.md).
- **Past tasks:** retry bugfix, duration parsing, multi-file Decimal ledger, and security-critical JWT HS256 verification.
- **Design:** four prompts × four tasks × three isolated repetitions = **48 Kimi Code runs**, sequential for cleaner wall-time comparisons.
- **Quality:** hidden tests run against copied artifacts in clean evaluation directories, followed by identity-stripped DeepSeek code review.
- **Efficiency:** total/input/output tokens, tool calls, LOC, wall time, expected tokens per successful attempt, and expected seconds per successful attempt.
- **Selection:** reliability first, then Pareto comparison of blind quality, tokens, and time. No weighted winner is declared when the quality arms are statistically indistinguishable.

**Results:** pending completion of the 48-run study. The single V3 smoke attempt passed the retry task in 48.33s with 72,205 total tokens, 1,464 output tokens, four tool calls, and 21 LOC; this is a runner validation, not a comparative result.

During the initial full run, 11 of the first 12 valid attempts passed and one V3 financial-task attempt timed out. Seven subsequent cells hit Kimi OAuth DNS/timeout errors or a transient refresh-lock conflict. Those cells are excluded from quality scoring rather than counted as prompt failures. The runner now retries infrastructure errors with exponential backoff, resets partial work before each retry, resumes valid cells, and writes a clean `results_final.jsonl`.

## DeepSeek V4.1 Flash 1017 Ultrafast lane

`deepseek/deepseek-v4.1-flash-1017-ultrafast` is the **same October 17 model revision** served through Fireworks' accelerated endpoint. It is not an abliterated fine-tune. The relevant comparison is accelerated serving versus standard 1017 serving, with abliterated 1017 retained as a separate arm where useful.

Live public [Vercel AI Gateway endpoint data](https://ai-gateway.vercel.sh/v1/models/deepseek/deepseek-v4.1-flash-1017-ultrafast/endpoints) at inspection time:

| Serving arm | Median throughput | Median TTFT | Input / 1M | Output / 1M |
|---|---:|---:|---:|---:|
| Fireworks 1017 Ultrafast | **1,115 tok/s** | 886ms | $2.40 | $9.60 |
| Fireworks standard 1017 | 322 tok/s | 1,417ms | $0.30 | $1.20 |

Ultrafast therefore showed about **3.46× median throughput at 8× token price**. That does not imply 3.46× faster agent completion: tool latency, turns, input processing, reasoning length, and reliability can dominate. Quality and end-to-end agent time must be measured on identical tasks. Public throughput also varies over time and is not a substitute for local measurements.

Standard 1017 is available through [LLM Gateway](https://llmgateway.io/models/deepseek-v4.1-flash-1017) and multiple Vercel providers. LLM Gateway also lists the distinct abliterated [DeepSeek V4.1 Flash Cyber](https://llmgateway.io/models/deepseek-v4.1-flash-cyber) as Enterprise-only.

### Model comparison runner

Use [`scripts/run_round5_model_bakeoff.py`](../scripts/run_round5_model_bakeoff.py) for the three serving arms: PaymentRequired abliterated, Vercel standard 1017, and Vercel 1017 Ultrafast. It uses the same four hidden-test tasks, V3, sequential repetitions, and token/time-per-pass metrics. `--check` reports endpoint readiness without running trials. The Vercel arms require `AI_GATEWAY_API_KEY`; no credential is stored in the repository.

### Measured abliterated baseline

The PaymentRequired abliterated arm completed **12/12 hidden-test passes** across the four tasks with V3 and `high` reasoning:

- **15,964.8** mean total tokens; **1,812.6** mean output tokens.
- **15.56s** mean wall time; **118.96 output tokens/s** measured across the complete agent run (not provider decode TPS).
- **39.5** mean LOC.
- **15,964.8 tokens and 15.56s expected per successful attempt** (pass rate was 100%).

Raw results: [`rounds/round5/model_abliterated_results.jsonl`](../rounds/round5/model_abliterated_results.jsonl) and [`model_abliterated_summary.json`](../rounds/round5/model_abliterated_summary.json). PaymentRequired returned no dollar-cost telemetry; the recorded zero means **unreported**, not free. Standard and Ultrafast 1017 must match this quality baseline before their serving gains can be assessed.

### Local access status

- PaymentRequired returned `404 Unknown model` for both `deepseek-v4.1-flash-1017-ultrafast` and `deepseek/deepseek-v4.1-flash-1017-ultrafast`; standard 1017 was also unavailable there.
- Pi has ready `paymentrequired` and `allmodels` credentials, but no ready Vercel AI Gateway, Fireworks, or LLM Gateway credentials.
- **Ultrafast quality runs are blocked on endpoint access, not on benchmark code or model existence.** No quality claim is made until those runs execute.

## Update protocol

1. Preserve raw per-run telemetry and anonymized judgments.
2. Report attempts, completion rate, all-attempt reliability, and infrastructure failures separately.
3. Never compare a completed patch's score with an incomplete patch's gate count as though they were equivalent.
4. Prefer expected tokens/time per successful solve over average tokens/time alone.
5. Update this report, the root `CHANGELOG.md`, and the prompt-blog `CHANGELOG.md` in the same change.
6. Change global agent instructions only after a repeated current-harness comparison supports the rollout.
