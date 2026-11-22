# Changelog

All notable benchmark rounds, harness engineering fixes, model catalog audits, and local optimization findings for `open-frontier-swe-bench` are documented here.

---

## [2026-11-22] — Living Prompt, Speed & Reliability Benchmark

### Added
- **V4a experimental default:** Published [`prompts/V4a_tldr_caveman.md`](prompts/V4a_tldr_caveman.md) in the root README while retaining V3 as the measured baseline. V4a is now active in global Kimi `AGENTS.md` and verified in a fresh rendered prompt; controlled thinking runs use a pre-rollout prompt snapshot.
- **48-run prompt result:** stock led hidden tests (**12/12**), blind quality (**89.75**), and estimated tokens/pass (**97,135**); V3 was fastest (**75.49s**); V4a produced the least code (**29.2 LOC**) but scored **83.08** with **118,759** estimated tokens/pass. V4a is therefore an experimental default, not the measured quality winner. Full artifacts are in `rounds/round5/`.
- **Trajectory analysis:** V4a averaged **6,335** reasoning characters versus **5,071** for V3. DeepSeek searched parent directories in all three financial runs. Added [`prompts/V5_clear_action_contract.md`](prompts/V5_clear_action_contract.md) to test explicit action order/scope and visible smoke checks against confusion-driven work.
- **V6 removes unproven prompt machinery:** [`prompts/V6_operational_minimalism.md`](prompts/V6_operational_minimalism.md) drops CAVEMAN/ADHD/TLDR/persona anchors and `reuse first`. It prioritizes correctness, root-cause changes, scoped inspection, focused verification, and stopping. V5's reuse rationale was a hypothesis, not a benchmark result; V6 remains inactive pending controlled measurements.
- [`prompts/V4c_adaptive_effort.md`](prompts/V4c_adaptive_effort.md): Next candidate for reliable minimalism—start terse, then think deeper and iterate only when blocked, uncertain, or failing tests. Kimi `low`/`high`/`max` thinking comparisons are planned as a separate factor.
- [`research/2026_11_PROMPT_SPEED_LIVING_BENCHMARK.md`](research/2026_11_PROMPT_SPEED_LIVING_BENCHMARK.md): Canonical GitHub-native continuation of the prompt-efficiency blog, with explicit separation of published results, fresh replication evidence, pending experiments, and blocked model lanes.
- [`scripts/run_round5_prompt_bakeoff.py`](scripts/run_round5_prompt_bakeoff.py): 48-run sequential Kimi Code comparison of stock, V3, TLDR-Caveman, and TLDR + thinking-budget prompts across four past tasks, with three repetitions, hidden tests, identity-stripped code review, token/time-per-pass metrics, and raw telemetry.
- [`scripts/run_round5_model_bakeoff.py`](scripts/run_round5_model_bakeoff.py): Reusable three-arm DeepSeek runner for PaymentRequired abliterated, Vercel standard 1017, and Vercel 1017 Ultrafast, with readiness checks and identical hidden-test tasks.
- [`prompts/V4a_tldr_caveman.md`](prompts/V4a_tldr_caveman.md) and [`prompts/V4b_tldr_think_budget.md`](prompts/V4b_tldr_think_budget.md): Controlled next-generation candidates from the prompt lab.
- DeepSeek V4.1 Flash 1017 Ultrafast serving analysis: public Vercel telemetry showed **1,115 tok/s** median throughput versus **322 tok/s** for standard Fireworks 1017, at **8× token price**. Local quality runs await compatible gateway access; PaymentRequired returned `404 Unknown model`.

### Verified
- The published V3 prompt in this repository is byte-identical to the original prompt-blog winner.
- V3 is globally active in Pi but **not** globally configured in Kimi Code; the benchmark injects it explicitly.
- Fresh Arkade V3 attempts did not reproduce the earlier 7/7 result: four attempts timed out at 600s with incomplete 1/7, 3/7, 4/7, and 3/7 gate outcomes. This motivates repeated controlled comparisons and is not presented as a controlled prompt regression.
- DeepSeek abliterated baseline completed **12/12** hidden-test passes at **15.56s** and **15,964.8 total tokens** per task on average; raw telemetry is preserved in `rounds/round5/`. Standard and Ultrafast 1017 comparisons remain pending gateway access.
- Hardened the prompt runner after Kimi OAuth DNS/timeout/refresh-lock failures: infrastructure cells are excluded and retried with backoff, partial work is reset, valid cells resume, and final results are written separately from the attempt log.

---

## [2026-11-19] — Round 4 Hermetic Benchmark & Sandbox-Leak Postmortem

### Security & Benchmark Integrity Fix
- **Critical Sandbox-Leak Discovery (Round 4 Initial Run, Invalidated):** Using `git worktree` shared `.git/worktrees` metadata with the host repo. In the un-sandboxed initial run, `R4_P2_dream_ml4_rev` (`dsh` worker) ran `git worktree list`, discovered `/tmp/subtasks/st3_gold/gold_final.patch`, and ran `git apply` at step 35 — producing a fake `95/100` score. The entire un-sandboxed run was invalidated and discarded.
- **4-Layer Hermetic Isolation ([`scripts/run_round4_beat_gold.py`](scripts/run_round4_beat_gold.py)):**
  1. Standalone `git clone` built from a clean `git archive` snapshot (`git remote remove origin`, zero shared worktree metadata).
  2. macOS kernel `sandbox-exec` profile blocking read/write access to `/private/tmp/subtasks`, `open-frontier-swe-bench`, original host repo, `.worktrees`, `_arkade_v4`, host session logs, host skills dirs, and all sibling candidate worktrees.
  3. Isolated temporary `DSH_HOME` & `KIMI_CODE_HOME` per invocation (zero prior session history, zero skill injection).
  4. Verified live with `dsh` smoke test (`git worktree list` shows only own clone; `ls /private/tmp/subtasks` returns `Operation not permitted`).
- **Fixed Round 4 Eval & Provider Routing ([`scripts/eval_blind_round4.py`](scripts/eval_blind_round4.py)):**
  - Routed DeepSeek-V4.1 workers (`dsh` & `pi`) to `nous/deepseek/deepseek-v4.1-flash-1017` after `402router`/`allmodels` returned `503 auth_unavailable`.
  - Fixed parallel Slice-A prompt to target `scripts/fixtures/*` directly (eliminating duplicate fixture dirs).
  - Lowered blind judge `claude-fable-5.2` `maxTokens` override from `65536` to `8192` (`--thinking medium`) to prevent Nous API `402` credit pre-reservation errors, and added explicit error raising on empty judge output.

### Added — Round 4 Hermetic Results (`rounds/round4/`)
- **8/8 strictly open-weights pipelines** executed under full hermetic isolation (`6/8` = `75%` passed all `7/7` deterministic gates; `0%` gold-patch leakage):
  - **#1 `R4_P4_parallel_dsh_gold_parity`** (`kimi-cli` -> `[2x dsh || -> dsh]` -> `[pi(k3.1) || pi(ml4)]` -> `dsh`): **`90/100`** (`7/7` gates, `5.51M` tok, `1,090s`, `1,657` LOC) — best security hardening (`redirect: "error"`, `:7081` & `/v1/admin` guards in config + client).
  - **#2 `R4_P1_dream_kimi_rev`** (`kimi-cli` -> `dsh` -> `pi(k3.1)` -> `dsh`): **`88/100`** (`7/7` gates, `6.36M` tok, `974s`) — beat `mistral-large-4-0` single reviewer (`R4_P2`, `84/100`) by `+4` pts.
  - **#3 `R4_P6_lean_pi_dual_rev`** (`kimi-cli` -> `pi(ds-v4.1)` -> `[pi(k3.1) || pi(ml4)]` -> `pi(ds-v4.1)`): **`85/100`** (`7/7` gates) at **`2.49M` tokens** (`-55%` tokens vs `#1`, `-73%` vs Round 3 `#1`).
  - **#4 `R4_P2_dream_ml4_rev`**: **`84/100`** (`7/7` gates, `1,111` LOC — leanest client).
  - **#5 `R4_P8_parallel_hetero_kimi_ds`**: **`83/100`** (`7/7` gates, `3.77M` tok).
  - **#6 `R4_P3_dream_dual_rev`**: **`82/100`** (`7/7` gates, `3.88M` tok).
  - **#7 `R4_P5_parallel_pi_lean`**: **`77/100`** (`6/7` gates — failed `G2` due to non-spec `index: 0` in template).
  - **#8 `R4_P7_minimax_m31_worker`** (`MiniMax-M3.1-Flash`): **`69/100`** (`6/7` gates — passed `G2..G7` incl. live HTTP auth/IDOR, failed `G1_own_tests`).
- **Diagnostic on Remaining `5`-pt Gap to `95/100` Gold Anchor:** Fable noted both genuine hardening gaps (config-time URL/port-7081 validation + whitelisted delegation view) and diff truncation (`24 KB` cap hid `ArkadeServer.js` & tests on larger diffs — to be fixed via per-file/pairwise blind judging in Round 5).

---

## [2026-11-19] — Cross-Benchmark Harness Synthesis (`947a6f1`)

### Added
- [`research/HARNESS_SYNTHESIS_PI_DURABLE_VS_CLI.md`](research/HARNESS_SYNTHESIS_PI_DURABLE_VS_CLI.md): Reconciled `eminogrande/pi-durable-swarm` (`ep2`/`ep3`) with `open-frontier-swe-bench` Round 3 (`pi --no-skills` used `15.5×` fewer tokens than OpenCode).
- Ported **Verbatim Spec Rule** and **Hard `onYield` Deterministic Test Gate** (up to 2 auto-heal retries before adversarial review) into [`scripts/run_round4_beat_gold.py`](scripts/run_round4_beat_gold.py).

---

## [2026-11-19] — Nov-19 Open-Frontier Catalog, `harness-hub` RL LoRA & Local M4 Optimization (`1aeacbf`)

### Added
- Updated [`research/2026_11_OPEN_FRONTIER_CATALOG.md`](research/2026_11_OPEN_FRONTIER_CATALOG.md) with live Nov-19-2026 Hugging Face audit across 10 labs: `XiaomiMiMo/MiMo-V2.6-Pro-RL`, `stepfun-ai/Step-5-Preview`, `MiniMaxAI/MiniMax-M3.1-Flash`, `Qwen/Qwen3.8-Flash-Next`, `tencent/Hy4-flash`, `inclusionAI/Ring-2.6-1T`, and Hugging Face's **`harness-hub/Qwen3.8-27B-pi-adapted`** AsyncGRPO LoRA (`39.2% -> 64.7%` SWE-bench Pro with thinking OFF, `4.5×` fewer tokens).
- [`research/LOCAL_M4_DEEPSEEK_QWEN_OPTIMIZATION.md`](research/LOCAL_M4_DEEPSEEK_QWEN_OPTIMIZATION.md): Empirical Apple M4 (16 GB) `llama-server` Metal optimization for `DeepSeek-V4-Pro-Qwen3.5-9B` (`14.6 -> 24.6 tok/s`, peak `29.4 tok/s`, `+68.5%` via embedded `draft-mtp` + DRY + `6.0 GB` swap-safe KV/checkpoints).
- Initial Round 4 runner & evaluator scripts (`scripts/run_round4_beat_gold.py`, `scripts/eval_blind_round4.py`).

---

## [2026-11-19] — Round 3 Native CLI Harnesses × Open-Frontier Models (`f2bde54`)

### Added
- Benchmarked 5 native CLI coding harnesses headlessly (`dsh 0.2.1-rc.5`, `kimi-code 2.5.2`, `vibe 3.1.3`, `opencode 1.19.3`, `pi 1.5.2`) across 10 pipelines (`rounds/round3/`).
- **Winner:** `R3_H8_combo_native_dream_team` (`kimi-cli(k3.1-hs)` -> `dsh(ds-v4.1)` -> `vibe(ml4)` -> `dsh(ds-v4.1)`) scored **`91/100`** (`7/7` gates), followed by solo `kimi-code` (`87/100`, `884` LOC) and solo `pi` + `kimi-k3.1-pro` (`86/100`, `4.28M` tok).
- **Fixed** Gate 5 stub `executord` in [`scripts/eval_blind_st4.py`](scripts/eval_blind_st4.py) to accept Go `meshapi` protojson `snake_case` + `camelCase` parity (`template_id` / `templateId`, `expires_at` / `expiresAt`).

---

## [2026-11-18] — Round 1 & Round 2 Baseline & Expanded Contenders (`ca27fd0`, `45bf923`)

### Added
- Established double-blind SWE evaluation protocol on frozen `nuri-com/nuri-server-musig2-v4-arkade` @ `136a54fa` with 7 deterministic gates and Closed-Frontier Gold reference (`95/100`, `7/7` gates, `closed_frontier_reference/`).
- **Round 1 (`rounds/round1/`, 6 pipelines on `pi`):** Solo `deepseek-v4.1-flash-abliterated` (`153 tok/s`) won **`91/100`** (`7/7` gates, `380s`); `C3_hetero_k3_ds_glm` scored **`88/100`** (`7/7` gates).
- **Round 2 (`rounds/round2/`, 10 pipelines on Nous):** Audited `Mistral-Large-4-0`, `Qwen3.8-2.4T`, `Qwen4-Max`, `DeepSeek-V4-Pro`, `Devstral-2`, and `Muse-Spark-Open` (`0/10` reached `7/7`, best `58/100`), proving throughput + agentic tool discipline beat raw parameter count.
