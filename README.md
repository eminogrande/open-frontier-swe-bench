# Open-Frontier SWE Multi-Agent & Native-Harness Benchmark (`open-frontier-swe-bench`)

Empirical, double-blind software-engineering benchmark finding the **best strictly OPEN-FRONTIER model + CLI harness stack** across **Planner -> Worker -> Reviewer -> Orchestrator** — using a **Closed-Frontier Gold PR (`95/100`, `7/7` gates)** solely as the target bar to beat.

Every round is committed here with full raw stage-by-stage telemetry, unified `.patch` diffs, anonymized blind-judge mappings, runner harnesses, and open-weights catalog audits. See [`CHANGELOG.md`](CHANGELOG.md) for chronological updates, fixes, and security postmortems.

---

## Round 7 — Telegraphic Caveman + ADHD Bakeoff (`rounds/round7/`) — `V8` (`P8c_ultra_oneshot`) Wins

**Production recommendation:** [`prompts/V8_telegraphic_adhd.md`](prompts/V8_telegraphic_adhd.md) (**586 chars / ~146 tokens**), verified across **72 runs, 4 frontier labs, and 6 model/effort configs** (`Gemini 4 Neon XHigh/High`, `Gemini 4 Hydrogen High`, `Claude Sonnet 5.5 High`, `DeepSeek V4.1 Flash`, `Kimi K3.1 Pro`) on `S1` (deploy log), `S2` (rambling chat anti-mirroring), and `H2` (JWT security):

```text
Ultra-terse caveman ADHD (off on "stop adhd mode"). Drop articles (a/an/the), filler, pronouns, helper verbs, full sentences, bold labels. Never mirror chatty prose. Max 3 numbered lines (`1. 2. 3.`), tiny numbered table only to compare columns.
Format:
Fixed: auth timeout.
1. Pool maxed at 10 (`db.py:18`)
2. Raised cap to 50; tests 12/12 pass
Next: deploy staging?

Code: read once, root cause only, reuse stdlib, smallest boring diff, no speculative abstractions. Keep correctness, security, 1 minimal test.
Batch parallel tools; quiet output; normal prose in docs/commits/warnings.
```

| Variant | Size | H2 Pass (all 6) | `agy` Words | `agy` Filler Hits | `agy` Bold Fluff | `agy` Soup | Router Think tok | Router Total tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `V7` (numbered prose) | 138 tok | 6/6 | 84.6 | 1.8 | 0.4 | 36.5 | 686 | 13,010 |
| `P8a` (rules only) | 145 tok | 6/6 | 77.0 | 0.9 | 0.0 | 77.4 | 147 | 9,847 |
| `P8b` (1-shot, no cap) | 136 tok | 6/6 | 94.0 | 1.2 | 0.1 | 100.6 | 146 | 9,414 |
| **`V8` (`P8c_ultra_oneshot`)** | **146 tok** | **6/6 (100%)** | **62.2 (-26%)** | **0.5 (-72%; 0.0 on Gemini 4)** | **0.0** | **22.9 (-37%)** | **92 (-87%)** | **8,789 (-32%)** |

**Why `V8` works (research-backed):** Combining `Chain-of-Draft` / `Caveman` syntactic drops (no articles/filler/bold labels), a structural cap (`Max 3 numbered lines` — never numeric word caps, which spiked XHigh thinking 7× in Round 6), and a **4-line telegraphic style anchor** breaks RLHF's prose-sentence habit via in-context imitation instead of CoT constraint loops.

---

## Round 6 — 6-Company Frontier Prompt Bakeoff (`rounds/round6/`) — `V7` (`V6` + Scannable ADHD Shape)

**Production recommendation:** [`prompts/V7_adhd_scannable.md`](prompts/V7_adhd_scannable.md) (**531 chars / ~133 tokens**), built directly on the Round 6 Pareto winner [`V6`](prompts/V6_human_caveman_minimal.md) (146 valid runs, 6 frontier labs, 9 model/effort configs, dual blind judges) and verified on `agy` (`3/3` H2 pass, `42.7s` mean wall — faster than V6 `49.5s`, zero overthinking spike, `Neon` soup `3`) to enforce a strict scannable ADHD layout instead of prose paragraphs:

```text
ADHD caveman format (off on "stop adhd mode"): never mirror chatty prose; no paragraphs.
Shape: 1-line outcome, up to 3 short numbered lines (tiny numbered table only to compare columns), optional "Next:" line. Plain spoken words; skip filler and raw dumps unless asked.
Code like a lazy senior dev: read touched code once, fix root causes, reuse existing code and stdlib, smallest boring diff, no speculative abstractions. Keep correctness, security, and one minimal test.
Batch parallel tools; quiet output; normal prose in docs, commits, and warnings.
```

### Native `agy` Harness (86 valid runs — Neon/Hydrogen XHigh & High, Sonnet 5.5, GPT-OSS 120B)

| Prompt | Size | SWE Pass | Blind SWE | Blind Human | LOC | Think tok | Exp tok/pass | Wall | Robot Soup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `P0_stock` | 0 tok | 8/10 (80%) | 79.7 | 23.7 | 180.1 | 8,794 | 94,100 | 125.3s | 221.4 |
| `P1_v3_current` | 121 tok | 10/11 (91%) | **83.1** | 55.1 | **150.6** | **5,131** | **57,161** | **89.9s** | 57.0 |
| `P3_ultra_minimal` | 157 tok | 10/12 (83%) | 81.0 | **85.9** | 162.0 | 9,216 | 78,972 | 131.6s | **9.3** |
| **`V6` (`P5_zero_overthink`)** | **112 tok** | **11/12 (92%)** | **81.0** | **66.3** | **150.9** | **7,020** | **63,202** | **110.6s** | **19.6** |
| `P6_micro` | **65 tok** | 10/11 (91%) | 82.4 | 78.2 | 160.4 | 8,244 | 74,595 | 118.5s | 17.0 |

### Open-Weights Router (`pi`, 60 valid runs — DeepSeek V4.1, Kimi K3.1 Pro, GLM 5.4)

| Prompt | Size | SWE Pass | Blind SWE | Blind Human | LOC | Think tok | Exp tok/pass | Wall | Robot Soup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `P0_stock` | 0 tok | 7/9 (78%) | 66.2 | 26.9 | 113.1 | 5,966 | 286,852 | 123.8s | 69.3 |
| `P1_v3_current` | 121 tok | **9/9 (100%)** | **82.2** | **66.5** | 106.9 | **2,311** | 104,449 | **83.8s** | 19.9 |
| `P3_ultra_minimal` | 157 tok | 7/9 (78%) | 69.8 | 61.0 | **92.4** | 4,088 | 92,536 | 114.0s | **15.4** |
| **`V6` (`P5_zero_overthink`)** | **112 tok** | **8/9 (89%)** | **75.1** | **62.2** | **93.4** | **3,708** | **88,822** | **102.2s** | 41.0 |
| `P6_micro` | **65 tok** | 7/9 (78%) | 65.0 | 59.8 | 96.3 | 3,131 | 151,383 | 117.6s | 21.0 |

**Key findings:**
- **Zero SWE degradation, highest `agy` pass rate (`92%`):** `V6` (`P5_zero_overthink`) passes **19/21 (90.5%)** combined vs **15/19 (79%)** stock, cuts expected tokens/pass **-33% (`agy`) / -69% (router)**, cuts thinking tokens **-20% (`agy`) / -38% (router)**, and cuts code LOC **-17%**.
- **Fixes V3's "robot log soup" without overthinking:** Cuts `agy` robot soup **-91%** vs stock (`19.6` vs `221.4`) and **-66%** vs V3 (`57.0`), lifting Blind Human readability from `23.7` (stock) / `55.1` (V3) to `66.3`.
- **Hard word caps cause 7× overthinking on XHigh:** Early `S1` ablation (`rounds/round6/agy_s1_overthink_ablation.json`) proved numeric word caps (`<=12 words each`) + ban lists (`P2`/`P4`) spiked reasoning tokens **7×** (`3,038–3,272` vs `453` stock — peaking at `11,573` on Hydrogen XHigh for a 38-word reply). Removing numeric caps fixed it.

---

## Round 5 Real-Task Evaluation — Stock Restored

**No custom prompt is active globally.** The V4a rollout and subsequent prompt-variant work were stopped because they did not demonstrate better real quality or reasoning efficiency. V3 and the measured variants remain historical artifacts only, not production recommendations.

The optimization target is **reliable minimalism**: hidden-test and blind quality first, then less code, fewer visible words, fewer reasoning tokens, and less wall time per successful solve. Current evaluation uses the real Arkade brownfield task and its seven deterministic gates with stock Kimi at `low`/`high`/`max` thinking; no new prompt text is being invented or tested.

| Prompt | Hidden passes | Blind /100 | LOC | Est. tokens/pass | Mean wall |
|---|---:|---:|---:|---:|---:|
| **Stock** | **12/12** | **89.75** | 39.5 | **97,135** | 98.55s |
| V3 | 11/12 | 83.58 | 31.9 | 105,609 | **75.49s** |
| **V4a** | 11/12 | 83.08 | **29.2** | 118,759 | 79.70s |
| V4b | **12/12** | 85.83 | 34.8 | 116,325 | 84.58s |

Stock led quality and expected tokens/pass; V3 was fastest; V4a produced the least code but did not reduce thought or total tokens. The V4a global rollout has been reverted. Full artifacts live in `rounds/round5/`.

Current work compares only Kimi `low`/`high`/`max` thinking under stock instructions on the real Arkade task. Trajectory analysis showed that V4a increased reasoning characters, while DeepSeek repeatedly hunted for unavailable tests; fixture clarity, visible checks, and harness isolation are being addressed directly rather than through additional prompt variants.

See the [living research report](research/2026_11_PROMPT_SPEED_LIVING_BENCHMARK.md) and [changelog](CHANGELOG.md) for current evidence, Ultrafast DeepSeek serving results, infrastructure exclusions, and future confirmation rounds.

---

## Round 4 Results (`rounds/round4/`) — Hermetic Sandboxed Parallel & Dual-Review Pipelines

> **Sandbox-Leak Postmortem & Hermetic Fix (2026-11-19):** An initial un-sandboxed Round 4 run using `git worktree` was **invalidated and discarded** after forensic audit caught `R4_P2` (`dsh`) running `git worktree list` and applying `/tmp/subtasks/st3_gold/gold_final.patch` (`95/100` fake). Round 4 below was re-run from scratch under **4-layer hermetic isolation** ([`scripts/run_round4_beat_gold.py`](scripts/run_round4_beat_gold.py)): standalone `git archive` -> `git clone` (zero worktree metadata), macOS kernel `sandbox-exec` blocking all reference/host/sibling dirs, and ephemeral `DSH_HOME`/`KIMI_CODE_HOME` with zero skills (`0%` gold-patch leakage verified).

| Rank | Pipeline | Open Weights? | Architecture (`Planner -> Worker(s) -> Review -> Finisher`) | Gates (`7`) | Blind Score (`/100`) | Wall (`s`) | Tokens | LOC |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| *Target* | `GOLD_carbon_fable` *(Closed Ref)* | No | `3x gemini-4-carbon -> claude-fable-5.2` | **`7/7`** | **`95/100`** | `~190s` | `~145K` | `~1,150` |
| **1** | `R4_P4_parallel_dsh_gold_parity` | **Yes** | `kimi-cli(k3.1-hs)` -> `[2x dsh(ds-v4.1) \|\| -> dsh]` -> `[pi(k3.1) \|\| pi(ml4)]` -> `dsh` | **`7/7`** | **`90/100`** (`C:23 S:23 B:21 T:22`) | `1,089.9s` | `5,509,380` | `1,657` |
| **2** | `R4_P1_dream_kimi_rev` | **Yes** | `kimi-cli(k3.1-hs)` -> `dsh(ds-v4.1)` -> `pi(k3.1-pro)` -> `dsh(ds-v4.1)` | **`7/7`** | **`88/100`** (`C:23 S:22 B:21 T:22`) | `973.9s` | `6,364,824` | `1,698` |
| **3** | `R4_P6_lean_pi_dual_rev` | **Yes** | `kimi-cli(k3.1-hs)` -> `pi(ds-v4.1)` -> `[pi(k3.1) \|\| pi(ml4)]` -> `pi(ds-v4.1)` | **`7/7`** | **`85/100`** (`C:23 S:19 B:21 T:22`) | `955.9s` | **`2,493,323`** | `1,284` |
| **4** | `R4_P2_dream_ml4_rev` | **Yes** | `kimi-cli(k3.1-hs)` -> `dsh(ds-v4.1)` -> `pi(ml4)` -> `dsh(ds-v4.1)` | **`7/7`** | **`84/100`** (`C:22 S:18 B:22 T:22`) | `874.0s` | `5,495,738` | **`1,111`** |
| **5** | `R4_P8_parallel_hetero_kimi_ds` | **Yes** | `kimi-cli(k3.1-hs)` -> `[kimi(cov) \|\| pi(cli) -> dsh(srv)]` -> `[pi(k3.1) \|\| pi(ml4)]` -> `dsh` | **`7/7`** | **`83/100`** (`C:21 S:20 B:21 T:21`) | `930.8s` | `3,768,411` | `1,403` |
| **6** | `R4_P3_dream_dual_rev` | **Yes** | `kimi-cli(k3.1-hs)` -> `dsh(ds-v4.1)` -> `[pi(k3.1) \|\| pi(ml4)]` -> `dsh(ds-v4.1)` | **`7/7`** | **`82/100`** (`C:21 S:20 B:20 T:21`) | `933.2s` | `3,876,056` | `1,300` |
| **7** | `R4_P5_parallel_pi_lean` | **Yes** | `kimi-cli(k3.1-hs)` -> `[2x pi(ds-v4.1) \|\| -> pi]` -> `[pi(k3.1) \|\| pi(ml4)]` -> `pi` | `6/7` *(G2)* | `77/100` (`C:17 S:22 B:17 T:21`) | **`839.3s`** | `3,482,286` | `1,670` |
| **8** | `R4_P7_minimax_m31_worker` | **Yes** | `kimi-cli(k3.1-hs)` -> `pi(minimax-m3.1-flash)` -> `pi(k3.1)` -> `pi(minimax-m3.1-flash)` | `6/7` *(G1)* | `69/100` (`C:19 S:17 B:19 T:14`) | `1,159.0s` | `5,879,114` | `1,100` |

**Round 4 Key Takeaways (Hermetic):**
- **Reliability Jump (`75%` `7/7` Pass Rate):** Porting the Verbatim Spec Rule + Hard `onYield` Test Gate + inline `--no-tools` `pi` Reviewers drove `6/8` pipelines to `7/7` deterministic gates (up from `6/10` in R3, `2/6` in R1, `0/10` in R2).
- **Parallel File-Scoped `dsh` + Dual Review Won (`90/100`):** `R4_P4_parallel_dsh_gold_parity` paired exact fixtures with full security hardening (`redirect: "error"`, `:7081` & `/v1/admin` guards in config + client) while cutting tokens `-39%` vs Round 3's `R3_H8` (`5.51M` vs `9.10M`).
- **Best Token Efficiency (`2.49M` tok, `7/7`):** `R4_P6_lean_pi_dual_rev` (`85/100`) used **`-73%` fewer tokens** than Round 3's `#1` (`R3_H8`).
- **Reviewer & Model Ranking:** `kimi-k3.1-pro` single reviewer (`R4_P1`, `88/100`) beat `mistral-large-4-0` single reviewer (`R4_P2`, `84/100`) by `+4` pts; `MiniMax-M3.1-Flash` (`69/100`, `6/7`) passed live HTTP Auth/IDOR (`G5`) and Go compiler (`G2`) but trails `DeepSeek-V4.1` (`82–90/100`).
- **Why `95/100` Gold Held:** Fable cited two gaps — remaining config-time URL/`:7081` & whitelisted-view inconsistencies, plus `24 KB` diff truncation hiding `ArkadeServer.js` & tests on larger diffs (Round 5 will use per-file/pairwise blind judging).

---

## Target Bar: Closed-Frontier Reference (`95/100`, `7/7` Gates — Excluded from Winner Selection)

- **Frozen Repo & Commit**: `nuri-com/nuri-server-musig2-v4-arkade` @ `136a54faa0c1af817cf9f829412582291a7ec83f`
- **Task (`prompts/TASK_PROMPT_arkade_172.md`)**: Server-side + 4-leaf Tapscript covenant slice of Issue `#172` (`NuriDelegatedVtxo` JCS SHA-256 `b9c74e80…`, `nuri_renew.json` `c6d690e1…`, minimal CScriptNum + BIP-68 CSV `seconds % 512 === 0` & bit-22 `1 << 22`, `ArkadeExecutorClient.js`, WebAuthn passkey -> MuSig2 `deriveAggregatedPk33` wallet-bound routes `POST /arkade/executor/delegation/register` & `/status`, anti-IDOR checks, live HTTP security tests).
- **System Skill (`prompts/V3_caveman_adhd_winner.md`)**: Winning `V3` (`CAVEMAN + ADHD MODE`) prompt (`-58.6%` token reduction in [`agent-prompt-brevity-bench`](https://github.com/eminogrande/agent-prompt-brevity-bench)).
- **Closed-Frontier Reference (`closed_frontier_reference/`)**: 3x parallel `google/gemini-4-carbon` workers + `anthropic/claude-fable-5.2` adversarial review (`88/100` v1 -> fixed `redirect: "error"`, route BIP-68 CSV bypass, and config URL log leak -> **`95/100`**, `7/7` gates).

---

## 7 Deterministic Gates (`SWE-bench` Style) + Double-Blind Arena Judge

1. `G1_own_tests`: Candidate's own `node --test src/ArkadeExecutorClient.test.js` passes (`rc=0`).
2. `G2_go_compiler_fixtures`: Real Go `arkade-os/delegatee/pkg/template` (`1aeb47a4`) parses `nuri_delegated_vtxo.json` (4 functions) and compiles `nuri_renew.json` (`template.Proof`).
3. `G3_encoding_and_jcs_invariants`: Exact minimal CScriptNum (`0 -> ""`, `144 -> "9000"`, `-1 -> "81"`), BIP-68 CSV (`512s -> "010040"`, `86400s` throws), and RFC-8785 JCS SHA-256 match.
4. `G4_uncertain_outcome_handling`: Network/timeout on `POST /v1/delegation` surfaces `EXECUTOR_OUTCOME_UNKNOWN` (`outcomeUnknown: true`).
5. `G5_live_http_auth_idor_security`: Live `ArkadeServer.js` subprocess against stub `executord` (accepting Go `meshapi` protojson `snake_case` + `camelCase` field parity) enforces `401` unauth, `401` purpose-scoped bootstrap token, `403` `client_recovery_key` spoofing, `200` bound registration (`ec3240` CSV hex), and `403` cross-wallet status IDOR.
6. `G6_existing_server_regression`: Existing `node scripts/notifications-bind-proof.mjs` passes (`rc=0`).
7. `G7_docs_and_no_admin_leak`: `ENDPOINTS.md` documents both routes; zero `/v1/admin` or `:7081` exposure in `ArkadeServer.js`.

All candidate diffs are stripped of model/harness/pipeline identity, shuffled with a fixed PRNG seed into `CANDIDATE_A..J`, and graded blindly by `anthropic/claude-fable-5.2` (`correctness_25`, `security_25`, `craft_brevity_25`, `tests_docs_25`) against the `95/100` Closed-Frontier anchor.

---

## Round 3 Results (`rounds/round3/`) — Native CLI Harnesses × Open-Frontier Models

Tested **5 CLI coding harnesses** headlessly on the exact same frozen commit & prompt:
- **`dsh 0.2.1-rc.5`** (`deepseek-ai/deepseek-harness`, official DeepSeek Harness, 283.7K★)
- **`kimi-code 2.5.2`** (official Kimi Code CLI + `kimi-code/k3.1-pro-highspeed`)
- **`vibe 3.1.3`** (`mistralai/mistral-vibe`, official Mistral Vibe CLI)
- **`opencode 1.19.3`** (`anomalyco/opencode`)
- **`pi 1.5.2`** (generic baseline harness at matched high-speed `133–153 tok/s` endpoints)

| Rank | Pipeline | Open Weights? | Harness × Model Architecture | Gates (`7`) | Blind Score (`/100`) | Wall (`s`) | Tokens | LOC |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| *Target* | `GOLD_carbon_fable` *(Closed Ref)* | No | `3x gemini-4-carbon -> claude-fable-5.2` | **`7/7`** | **`95/100`** | `~190s` | `~145K` | `~1,150` |
| **1** | `R3_H8_combo_native_dream_team` | **Yes** | `kimi-cli(k3.1-pro-hs)` -> `dsh(ds-v4.1-flash)` -> `vibe(ml4)` -> `dsh(ds-v4.1-flash)` | **`7/7`** | **`91/100`** (`C:24 S:23 B:21 T:23`) | `971.4s` | `9,101,980` | `1,408` |
| **2** | `R3_H1_kimi_cli_k3_hs` | **Yes** | Solo **`kimi-code 2.5.2`** + `kimi-code/k3.1-pro-highspeed` | **`7/7`** | **`87/100`** (`C:23 S:21 B:22 T:21`) | `483.0s` | `6,745,679` | **`884`** |
| **3** | `R3_H2_pi_k3_nous` | **Yes** | Solo **`pi 1.5.2`** + `nous/kimi-k3.1-pro` (`133 tok/s`) | **`7/7`** | **`86/100`** (`C:23 S:21 B:21 T:21`) | `485.8s` | **`4,284,586`** | `1,016` |
| **4** | `R3_H4_dsh_k3_nous` | **Yes** | Solo **`dsh 0.2.1-rc.5`** + `nous/kimi-k3.1-pro` | **`7/7`** | **`84/100`** (`C:22 S:21 B:20 T:21`) | `601.5s` | `7,797,918` | `956` |
| **5** | `R3_H5_dsh_ds_v4_1_fast` | **Yes** | Solo **`dsh 0.2.1-rc.5`** + `deepseek-v4.1-flash` (`153 tok/s`) | **`7/7`** | **`80/100`** (`C:21 S:19 B:19 T:21`) | `601.5s` | `12,700,954` | `1,422` |
| **6** | `R3_H6_opencode_ds_v4_1_fast` | **Yes** | Solo **`opencode 1.19.3`** + `deepseek-v4.1-flash` (`153 tok/s`) | **`7/7`** | **`79/100`** (`C:20 S:20 B:19 T:20`) | **`317.7s`** | `5,699,913` | `1,194` |
| **7** | `R3_H3_opencode_k3_nous` | **Yes** | Solo **`opencode 1.19.3`** + `nous/kimi-k3.1-pro` | `6/7` *(G2)* | **`76/100`** (`C:19 S:20 B:19 T:18`) | `601.5s` | `7,859,483` | `1,056` |
| **8** | `R3_H10_combo_qwen4_dsh` | No *(API)* | `pi(qwen4-max)` -> `dsh(ds-v4.1-flash)` -> `pi(qwen4-max)` -> `dsh(ds-v4.1-flash)` | `4/7` | `56/100` (`C:12 S:16 B:15 T:13`) | `540.7s` | `6,795,368` | `1,160` |
| **9** | `R3_H9_combo_dsh_unified` | **Yes** | `dsh(k3.1-pro)` -> `dsh(ds-v4.1-flash)` -> `dsh(ml4)` -> `dsh(ds-v4.1-flash)` | `3/7` | `45/100` (`C:9 S:12 B:13 T:11`) | `658.5s` | `8,676,814` | `1,235` |
| **10** | `R3_H7_vibe_ml4_native` | **Yes** | Solo **`vibe 3.1.3`** + `mistral-large-4-0` | `3/7` | `38/100` (`C:7 S:12 B:11 T:8`) | `590.7s` | `1,933,315` | `631` |

---

## Round 1 Results (`rounds/round1/`) — Baseline `pi` Harness (`paymentrequired` Router)

| Rank | Pipeline | Open Weights? | Architecture (`Planner -> Worker -> Reviewer -> Orch`) | Gates (`7`) | Blind Score (`/100`) | Wall (`s`) | Tokens |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| *Target* | `GOLD_carbon_fable` *(Closed Ref)* | No | `3x gemini-4-carbon -> claude-fable-5.2` | **`7/7`** | **`95/100`** | `~190s` | `~145K` |
| **1** | `C6_solo_deepseek_v4_1` | **Yes** | Solo `pi` + `deepseek-v4.1-flash-abliterated` (`153 tok/s`) | **`7/7`** | **`91/100`** (`C:24 S:23 B:21 T:23`) | **`380.1s`** | `8,784,093` |
| **2** | `C3_hetero_k3_ds_glm` | **Yes** | `k3.1-pro -> deepseek-v4.1-flash -> glm-5.3 -> deepseek-v4.1-flash` (`pi`) | **`7/7`** | **`88/100`** (`C:23 S:22 B:21 T:22`) | `865.4s` | **`7,014,140`** |
| **3** | `C5_hetero_nem_ds_k3` | **Yes** | `nemotron-3-ultra-550b -> deepseek-v4.1-flash -> k3.1-pro -> deepseek-v4.1-flash` | `4/7` | `41/100` (`C:8 S:9 B:12 T:12`) | `816.1s` | `4,573,588` |
| **4** | `C2_homo_k3_4stage` | **Yes** | `k3.1-pro x4` (`24 tok/s` slow endpoint) | `2/7` | `23/100` (`C:8 S:6 B:9 T:0`) | `1,401.9s` | `2,266,663` |
| **5** | `C4_hetero_glm_kimi_k3` | **Yes** | `glm-5.3 -> kimi-for-coding -> k3.1-pro -> kimi-for-coding` | `1/7` | `0/100` | `974.8s` | `2,666,593` |
| **6** | `C1_solo_k3_max` | **Yes** | Solo `k3.1-pro` (`24 tok/s` slow endpoint) | `1/7` | `0/100` | `600.1s` | `1,012,631` |

---

## Round 2 Results (`rounds/round2/`) — Nov 2026 Expanded Open-Frontier Contenders (`Nous`)

Full model audit in [`research/2026_11_OPEN_FRONTIER_CATALOG.md`](research/2026_11_OPEN_FRONTIER_CATALOG.md).

| Rank | Pipeline | Open Weights? | Architecture (`Planner -> Worker -> Reviewer -> Orch`) | Gates (`7`) | Blind Score (`/100`) | Wall (`s`) | Tokens |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **1** | `R2_C9_hetero_ml4_ds41_qwen2_4t` | **Yes** | `mistral-large-4-0 -> deepseek-v4.1-flash-1017 -> qwen3.8-2.4t-a95b -> deepseek-v4.1-flash-1017` | `5/7` | **`58/100`** (`C:15 S:14 B:14 T:15`) | `750.4s` | `2,815,486` |
| **2** | `R2_C7_hetero_qwen2_4t_ml4_k3` | **Yes** | `qwen3.8-2.4t-a95b -> mistral-large-4-0 -> kimi-k3.1-pro -> mistral-large-4-0` | `4/7` | **`54/100`** (`C:13 S:14 B:14 T:13`) | `997.3s` | `2,618,723` |
| **3** | `R2_C6_homo_ml4_4stage` | **Yes** | `mistral-large-4-0 x4` | `4/7` | **`49/100`** (`C:11 S:16 B:13 T:9`) | `1,133.8s` | `1,500,002` |
| **4** | `R2_C3_solo_qwen4_max` | No *(API)* | Solo `qwen/qwen4-max` | `3/7` | **`45/100`** (`C:12 S:13 B:13 T:7`) | `600.1s` | `800,227` |
| **5** | `R2_C10_hetero_dsv4pro_devstral_glm53` | **Yes** | `deepseek-v4-pro-0813 -> devstral-2512 -> glm-5.3-prime -> devstral-2512` | `4/7` | **`37/100`** (`C:8 S:9 B:9 T:11`) | `1,055.2s` | `6,712,608` |
| **6** | `R2_C8_hetero_k3_muse_ml4` | **Yes** | `kimi-k3.1-pro -> muse-spark-open -> mistral-large-4-0 -> muse-spark-open` | `3/7` | **`25/100`** (`C:6 S:5 B:6 T:8`) | `997.8s` | `3,468,815` |
| **7** | `R2_C1_solo_mistral_large_4` | **Yes** | Solo `mistralai/mistral-large-4-0` (1T/52B) | `1/7` | `7/100` | `600.1s` | `1,541,372` |
| **8** | `R2_C5_solo_deepseek_v4_pro` | **Yes** | Solo `deepseek/deepseek-v4-pro-0813` (1.6T) | `1/7` | `1/100` | `600.1s` | `2,382,680` |
| **9** | `R2_C4_solo_muse_spark_open` | **Yes** | Solo `meta/muse-spark-open` (816B/42B) | `1/7` | `1/100` | `2.0s` | `3,802` |
| **10** | `R2_C2_solo_qwen3_8_2_4t` | **Yes** | Solo `qwen/qwen3.8-2.4t-a95b` (2.4T/95B) | `1/7` | `1/100` | `243.4s` | `759,359` |

---

## Cross-Round Key Findings (34 Controlled Pipelines Across 4 Rounds)

1. **Harness × Model Matrix Proof (Round 3)**:
   - **Kimi K3.1 Pro Across Harnesses (`kimi-code` > `pi` > `dsh` > `opencode`)**: Once moved off Round 1's `24 tok/s` router bottleneck onto `k3.1-pro-highspeed` / `nous` (`133 tok/s`), `Kimi-K3.1-Pro` jumped from `0/100` to **`7/7` gates across three harnesses** — **Native `kimi-code 2.5.2` won on quality & craft (`87/100`, `884` LOC, `483s`)**, **`pi 1.5.2` won on token economy (`86/100`, `4.28M` tok — `-37%` fewer tokens than `kimi-code`, `486s`)**, **`dsh 0.2.1-rc.5` scored `84/100` (`7/7` gates)**, and **`opencode 1.19.3` scored `76/100` (`6/7` gates)**.
   - **DeepSeek V4.1 Flash Across Harnesses (`pi` > `dsh` solo > `opencode`, while `kimi-cli + dsh` tied #1 overall!)**:
     - As a **guided Worker + Finisher**, **`dsh` (`DeepSeek Harness 0.2.1-rc.5`) + `deepseek-v4.1-flash`** paired with **`kimi-code` (`k3.1-pro-highspeed`) Planner** (`R3_H8_combo_native_dream_team`) achieved **`91/100` (`7/7` gates)** and produced the **strongest security hardening of any open-model run across all 3 rounds** (`redirect: "error"`, 1 MiB response cap, config-load `:7081` & `/v1/admin` rejection, `recoveryStore` status fallback without in-process state).
     - As a **solo unguided agent**, lightweight **`pi 1.5.2` (`91/100`, `380s`, `8.78M` tok)** beat **`dsh` solo (`80/100`, `601s`, `12.70M` tok)** and **`opencode` (`79/100`, **`318s` fastest wall time**, `5.70M` tok)** because `dsh`'s richer agentic toolset caused unguided `deepseek-v4.1-flash` to take `124` turns (`+45%` tokens).
   - **Planner Harness Matters (`kimi-code` vs `dsh` on `Kimi-K3.1-Pro`)**: `kimi-code(k3.1-pro-hs)` Planner (`R3_H8`, `290K` tok, `22` tool calls) grounded exact invariants -> **`91/100` (`7/7` gates)**, whereas `dsh(k3.1-pro)` Planner (`R3_H9`, `460K` tok) omitted exact fixture schema details -> `45/100` (`3/7` gates).
   - **Mistral Vibe `3.1.3` (`R3_H7`) & `Qwen4-Max` (`R3_H10`)**: `vibe` improved `mistral-large-4-0` solo from `7/100` (`pi` in R2) to `38/100` (`+31` pts), and `vibe` timed out (`rc=3`) on inline 40KB `--no-tools` diffs due to scanning `~/.agents/skills`; `qwen4-max` Planner (`55K` tok, `7` tool calls) skipped reading upstream Go `delegatee` schemas (`56/100`, `4/7` gates).

2. **Recommended Strictly Open-Frontier Production Stack**:
   - **Maximum Security & Spec Fidelity (`91/100`, `7/7` gates — closest to `95/100` Closed Gold)**:
     - **Planner**: **`kimi-code 2.5.2` + `kimi-k3.1-pro-highspeed`** *(or `pi` + `nous/kimi-k3.1-pro`, read-only)*
     - **Worker**: **`dsh` (`deepseek-harness`) or `pi` + `deepseek-v4.1-flash`** *(at `150+ tok/s`)*
     - **Reviewer (`--no-tools` inline diff)**: **`pi` + `kimi-k3.1-pro` or `mistral-large-4-0`** *(never `vibe` for toolless inline review)*
     - **Orchestrator / Finisher**: **`dsh` or `pi` + `deepseek-v4.1-flash`**
   - **Sleekest Single-Agent Fast Mode**:
     - **`pi` + `deepseek-v4.1-flash`** (`91/100`, `7/7` gates, `380s`) OR **`kimi-code` + `k3.1-pro-highspeed`** (`87/100`, `7/7` gates, `483s`, cleanest `884` LOC) OR **`pi` + `nous/kimi-k3.1-pro`** (`86/100`, `7/7` gates, lowest **`4.28M` tokens**).

---

## Research & Optimization Docs (`research/`)
- [`research/2026_11_OPEN_FRONTIER_CATALOG.md`](research/2026_11_OPEN_FRONTIER_CATALOG.md): Live Nov-19-2026 HF audit across 10 labs — added `XiaomiMiMo/MiMo-V2.6-Pro-RL` (`89.9%` TB 2.1, `71.9%` DeepSWE), `stepfun-ai/Step-5-Preview` (`80.5%` ProgramBench), `MiniMaxAI/MiniMax-M3.1-Flash` (`73.7%` DeepSWE), `Qwen/Qwen3.8-Flash-Next` (`62.5%` SWE-Pro, 6B active), `tencent/Hy4-flash` (Nov 17), `inclusionAI/Ring-2.6-1T`, and Hugging Face's **`harness-hub/Qwen3.8-27B-pi-adapted`** RL LoRA (`64.7%` SWE-Pro w/ thinking OFF, `4.5×` fewer tokens).
- [`research/LOCAL_M4_DEEPSEEK_QWEN_OPTIMIZATION.md`](research/LOCAL_M4_DEEPSEEK_QWEN_OPTIMIZATION.md): Empirical Apple M4 (16 GB) optimization of `DeepSeek-V4-Pro-Qwen3.5-9B` (`14.6 -> 24.6 tok/s`, peak `29.4 tok/s`, `+68.5%` via embedded `draft-mtp` + DRY + 6.0 GB swap-safe checkpoints).
- [`research/HARNESS_SYNTHESIS_PI_DURABLE_VS_CLI.md`](research/HARNESS_SYNTHESIS_PI_DURABLE_VS_CLI.md): Cross-benchmark reconciliation with `eminogrande/pi-durable-swarm` (`ep2`/`ep3`: `pi-durable` `95.33/100`, `pi --no-skills` `41.9K` tok `15.5×` leaner than OpenCode) + porting Verbatim Spec Rule & Hard `onYield` Test Gate into Round 4.
- [`research/2026_11_PROMPT_SPEED_LIVING_BENCHMARK.md`](research/2026_11_PROMPT_SPEED_LIVING_BENCHMARK.md): Living GitHub-native prompt study covering V3 publication/global Kimi status, Arkade replication variance, the 48-run hidden-test + blind-review prompt bakeoff, and DeepSeek 1017 Ultrafast throughput/price/access evidence.
- **Round 4 Hermetic Complete (`rounds/round4/`, `scripts/run_round4_beat_gold.py`, `scripts/eval_blind_round4.py`)**: 4-layer `sandbox-exec` + `git archive`/`clone` hermetic isolation, Verbatim Spec + Hard `onYield` Test Gate, parallel file-scoped workers (`R4_P4` **`90/100`**, `7/7`), lean dual-review (`R4_P6` **`85/100`**, `2.49M` tok), and `MiniMax-M3.1-Flash` (`69/100`, `6/7`). See [`CHANGELOG.md`](CHANGELOG.md).

---

## Reproducing & Running Next Rounds

```bash
# Run deterministic 7-gate + blind Fable evaluation for any round
python3 scripts/eval_blind_round1.py
python3 scripts/eval_blind_round2.py
python3 scripts/eval_blind_round3.py
# Round 4 (beat 95/100 Gold target):
python3 scripts/run_round4_beat_gold.py && python3 scripts/eval_blind_round4.py
```
