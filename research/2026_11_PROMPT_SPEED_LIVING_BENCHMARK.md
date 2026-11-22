# Living Prompt, Model-Speed & Reliability Benchmark

**Status:** active real-task evaluation. Stock is the production configuration. Update this report and [`CHANGELOG.md`](../CHANGELOG.md) together when a measured round lands.

## Stock restored; prompt-variant work stopped

The V4a rollout was reverted and global `$KIMI_CODE_HOME/AGENTS.md` was removed. V4c/V5/V6 were not benchmarked and have been removed from the active repository. The small-task V4a/V4c thinking matrix was stopped. No new prompt variants will be introduced as recommendations without controlled evidence on real repository tasks.

The current independent variable is Kimi reasoning effort (`low`/`high`/`max`) under stock instructions, evaluated on Arkade by [`scripts/run_round5_arkade_stock.py`](../scripts/run_round5_arkade_stock.py). The existing hermetic Round 4 runner accepts an empty system-prompt extension and per-process effort while preserving its default behavior for prior pipelines.

## Representative confirmation suite

Small tasks are useful for cheap rejection, not for declaring a global coding default. Finalists should advance to a stratified suite:

1. **Brownfield integration:** the frozen Arkade `#172` task and its seven deterministic security/protocol gates.
2. **Real-repository repair:** a language-stratified DeepSWE v1.1 sample with offline execution and hidden tests.
3. **Systems and debugging:** a Terminal-Bench sample covering configuration, concurrency, and failing-toolchain diagnosis.
4. **Past greenfield work:** the earlier multi-file concurrency and debugging episodes, retaining their original hidden checks.
5. **Security and exact contracts:** authenticated routes, IDOR resistance, financial rounding, and exact output schemas.

Use three attempts per cell, report macro quality by task family, completion and all-three reliability, expected tokens/seconds per solve, and blind code review. Test `low`, `high`, and `max` thinking independently. An adaptive orchestration arm may start at `low`, escalate to `high` after a genuine visible-test failure, and reserve `max` for a second failure or long-horizon uncertainty; hidden tests must remain reserved for final scoring.

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

**Results:** 48 valid cells completed; 46 passed hidden tests. OAuth failures were excluded and retried, not counted as prompt failures. Four cells timed out; two timeout cells left passing code. Token means below use only runs with telemetry (`token runs`), while wall time and pass rates include every valid attempt. Expected tokens/pass adjusts the measured mean by the attempt pass rate and remains an estimate for arms with missing timeout telemetry.

| Prompt | Hidden passes | Timeouts | Blind /100 | LOC | Mean tokens (token runs) | Est. tokens/pass | Mean wall |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Stock** | **12/12** | 2 | **89.75** | 39.5 | 97,135 (10) | **97,135** | 98.55s |
| V3 | 11/12 | 1 | 83.58 | 31.9 | **96,808 (11)** | 105,609 | **75.49s** |
| **V4a** | 11/12 | 1 | 83.08 | **29.2** | 108,863 (11) | 118,759 | 79.70s |
| V4b | **12/12** | **0** | 85.83 | 34.8 | 116,325 (12) | 116,325 | 84.58s |

Raw artifacts: [`prompt_results.jsonl`](../rounds/round5/prompt_results.jsonl), [`prompt_summary.json`](../rounds/round5/prompt_summary.json), and `prompt_blind_*.json` in `rounds/round5/`.

**Interpretation:** stock is the quality and expected-token-per-pass leader on this small suite but has the slowest mean wall time. V3 is fastest and nearly ties stock on measured mean tokens, but has lower blind quality. V4a wins only code brevity; it did **not** reduce reasoning, tokens, or quality loss. V4b completed every run without a timeout but burned the most tokens. Three repetitions per task are enough to reject simplistic claims, not enough to establish a universal prompt winner. V4a remains the user-selected experimental global default, not the measured quality winner.

## Trajectory analysis: confusion versus useful thought

Analysis runner: [`scripts/analyze_round5_trajectories.py`](../scripts/analyze_round5_trajectories.py). Raw chain-of-thought is not published; the report retains aggregate reasoning length, interpretation/test-hunting signals, tool behavior, and useful correctness signals.

- **V4a did not shorten thought:** analyzable V4a runs averaged **6,335** reasoning characters versus **5,071** for V3, with more correctness deliberation and more brevity negotiation.
- **The financial task caused the worst reinterpretation:** the largest Kimi financial trace reached 23,980 reasoning characters; V4a's largest reached 15,117. This is a task-clarity problem as well as a prompt problem.
- **DeepSeek test hunting was concrete:** all three financial runs searched parent directories. One run spent **1,306 reasoning tokens** overall, including a long deliberation about data representation and unavailable tests, before implementing.
- **Useful thought exists:** Decimal rounding, signature boundaries, validation, and security reasoning should not be optimized away. Pattern counts are review signals, not automatic proof of waste.

These observations are now being tested through **fixture and harness changes**, not more prompt variants: visible smoke checks where appropriate, explicit task contracts, stock instructions, sibling isolation, and independent thinking-effort comparisons. The V5/V6 wording hypotheses were rejected before activation and removed from the active repository.

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
