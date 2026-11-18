# Open-Frontier SWE Multi-Agent Benchmark (`open-frontier-swe-bench`)

Empirical, double-blind software-engineering benchmark finding the **best strictly OPEN-FRONTIER model combination** across **Planner -> Worker -> Reviewer -> Orchestrator** — using a **Closed-Frontier Gold PR (`95/100`, `7/7` gates)** solely as the target bar to beat.

Every round is committed here with full raw stage-by-stage telemetry, unified `.patch` diffs, anonymized blind-judge mappings, runner harnesses, and open-weights catalog audits.

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
5. `G5_live_http_auth_idor_security`: Live `ArkadeServer.js` subprocess against stub `executord` enforces `401` unauth, `401` purpose-scoped bootstrap token, `403` `client_recovery_key` spoofing, `200` bound registration (`ec3240` CSV hex), and `403` cross-wallet status IDOR.
6. `G6_existing_server_regression`: Existing `node scripts/notifications-bind-proof.mjs` passes (`rc=0`).
7. `G7_docs_and_no_admin_leak`: `ENDPOINTS.md` documents both routes; zero `/v1/admin` or `:7081` exposure in `ArkadeServer.js`.

All candidate diffs are stripped of model/pipeline identity, shuffled with a fixed PRNG seed into `CANDIDATE_A..N`, and graded blindly (`correctness_25`, `security_25`, `craft_brevity_25`, `tests_docs_25`) against the `95/100` Closed-Frontier anchor.

---

## Round 1 Results (`rounds/round1/`) — Open-Weight Stack (`paymentrequired` Router)

| Rank | Pipeline | Open Weights? | Architecture (`Planner -> Worker -> Reviewer -> Orch`) | Gates (`7`) | Blind Score (`/100`) | Wall (`s`) | Tokens |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| *Target* | `GOLD_carbon_fable` *(Closed Ref)* | No | `3x gemini-4-carbon -> claude-fable-5.2` | **`7/7`** | **`95/100`** | `~190s` | `~145K` |
| **1** | `C6_solo_deepseek_v4_1` | **Yes** | Solo `deepseek-v4.1-flash-abliterated` | **`7/7`** | **`91/100`** (`C:24 S:23 B:21 T:23`) | **`380.1s`** | `8,784,093` |
| **2** | `C3_hetero_k3_ds_glm` | **Yes** | `k3.1-pro -> deepseek-v4.1-flash -> glm-5.3 -> deepseek-v4.1-flash` | **`7/7`** | **`88/100`** (`C:23 S:22 B:21 T:22`) | `865.4s` | **`7,014,140`** |
| **3** | `C5_hetero_nem_ds_k3` | **Yes** | `nemotron-3-ultra-550b -> deepseek-v4.1-flash -> k3.1-pro -> deepseek-v4.1-flash` | `4/7` | `41/100` (`C:8 S:9 B:12 T:12`) | `816.1s` | `4,573,588` |
| **4** | `C2_homo_k3_4stage` | **Yes** | `k3.1-pro x4` (Homogeneous) | `2/7` | `23/100` (`C:8 S:6 B:9 T:0`) | `1,401.9s` | `2,266,663` |
| **5** | `C4_hetero_glm_kimi_k3` | **Yes** | `glm-5.3 -> kimi-for-coding -> k3.1-pro -> kimi-for-coding` | `1/7` | `0/100` | `974.8s` | `2,666,593` |
| **6** | `C1_solo_k3_max` | **Yes** | Solo `k3.1-pro` max thinking | `1/7` | `0/100` | `600.1s` | `1,012,631` |

---

## Round 2 Results (`rounds/round2/`) — Nov 2026 Expanded Open-Frontier Contenders

Tested **10 new pipelines** covering the latest Oct/Nov 2026 releases (`mistralai/mistral-large-4-0` [Mistral Vibe engine], `mistralai/devstral-2512`, `qwen/qwen3.8-2.4t-a95b`, API-only `qwen/qwen4-max` [released 2026-11-16], `meta/muse-spark-open`, `deepseek/deepseek-v4-pro-0813`, `deepseek/deepseek-v4.1-flash-1017`, `moonshotai/kimi-k3.1-pro`, `z-ai/glm-5.3-prime`). Full model audit in [`research/2026_11_OPEN_FRONTIER_CATALOG.md`](research/2026_11_OPEN_FRONTIER_CATALOG.md).

| Rank | Pipeline | Open Weights? | Architecture (`Planner -> Worker -> Reviewer -> Orch`) | Gates (`7`) | Blind Score (`/100`) | Wall (`s`) | Tokens |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **1** | `R2_C9_hetero_ml4_ds41_qwen2_4t` | **Yes** | Planner mistral-large-4-0 -> Worker deepseek-v4.1-flash-1017 -> Reviewer qwen3.8-2.4t-a95b -> Orch deepseek-v4.1-flash-1017 | `5/7` | **`58/100`** (`C:15 S:14 B:14 T:15`) | `750.4s` | `2,815,486` |
| **2** | `R2_C7_hetero_qwen2_4t_ml4_k3` | **Yes** | Planner qwen3.8-2.4t-a95b -> Worker mistral-large-4-0 -> Reviewer kimi-k3.1-pro -> Orch mistral-large-4-0 | `4/7` | **`54/100`** (`C:13 S:14 B:14 T:13`) | `997.29s` | `2,618,723` |
| **3** | `R2_C6_homo_ml4_4stage` | **Yes** | mistral-large-4-0 x4 | `4/7` | **`49/100`** (`C:11 S:16 B:13 T:9`) | `1133.79s` | `1,500,002` |
| **4** | `R2_C3_solo_qwen4_max` | No *(API)* | qwen/qwen4-max | `3/7` | **`45/100`** (`C:12 S:13 B:13 T:7`) | `600.12s` | `800,227` |
| **5** | `R2_C10_hetero_dsv4pro_devstral_glm53` | **Yes** | Planner deepseek-v4-pro-0813 -> Worker devstral-2512 -> Reviewer glm-5.3-prime -> Orch devstral-2512 | `4/7` | **`37/100`** (`C:8 S:9 B:9 T:11`) | `1055.15s` | `6,712,608` |
| **6** | `R2_C8_hetero_k3_muse_ml4` | **Yes** | Planner kimi-k3.1-pro -> Worker muse-spark-open -> Reviewer mistral-large-4-0 -> Orch muse-spark-open | `3/7` | **`25/100`** (`C:6 S:5 B:6 T:8`) | `997.84s` | `3,468,815` |
| **7** | `R2_C1_solo_mistral_large_4` | **Yes** | mistralai/mistral-large-4-0 (1T/52B) | `1/7` | **`7/100`** (`C:5 S:0 B:2 T:0`) | `600.12s` | `1,541,372` |
| **8** | `R2_C5_solo_deepseek_v4_pro` | **Yes** | deepseek/deepseek-v4-pro-0813 (1.6T) | `1/7` | **`1/100`** (`C:0 S:0 B:1 T:0`) | `600.11s` | `2,382,680` |
| **9** | `R2_C4_solo_muse_spark_open` | **Yes** | meta/muse-spark-open (816B/42B) | `1/7` | **`1/100`** (`C:0 S:0 B:1 T:0`) | `2.02s` | `3,802` |
| **10** | `R2_C2_solo_qwen3_8_2_4t` | **Yes** | qwen/qwen3.8-2.4t-a95b (2.4T/95B) | `1/7` | **`1/100`** (`C:0 S:0 B:1 T:0`) | `243.41s` | `759,359` |

---

## Cross-Round Synthesis: Why "Different Brains" Win & Exact Open-Frontier Stack

1. **Every Solo Heavy-Reasoning Flagship Failed at `600s` on the 6,278-LOC Monolith**:
   - `kimi-k3.1-pro` solo (`0/100`), `deepseek-v4-pro-0813` solo (`1/100`), `qwen3.8-2.4t-a95b` solo (`1/100`), `mistral-large-4-0` solo (`7/100`), `muse-spark-open` solo (`1/100` — 1-turn tool-skip quirk), and API-only `qwen4-max` solo (`45/100`, `3/7` gates) **all stalled or timed out** when forced to read a 6.2K-line file, inspect upstream Go repos, implement 7 files, and debug live WebAuthn tests in one agent loop.
   - Only **`deepseek-v4.1-flash`** (`C6`: **`91/100`, `7/7` gates in `380s`**) had the tool-call throughput (`98` tool calls in `6.3` min) to inspect the upstream Go `arkade-os/delegatee` repo on disk AND complete all 7 files solo — at the cost of **8.78M tokens**.
2. **Heterogeneous "Different Brains" (`Planner -> High-TPS Worker -> Adversarial Diff Reviewer`) Dramatically Beat Solo on Token Efficiency & Beat Slow Workers**:
   - Pairing `mistral-large-4-0` Planner (`57s`, `106K` tok) -> `deepseek-v4.1-flash-1017` Worker -> `qwen3.8-2.4t-a95b` Reviewer (`R2_C9`) cut total tokens **-68%** (`2.82M` vs `8.78M` in `C6`), while `kimi-k3.1-pro` Planner -> `deepseek-v4.1-flash` Worker (`C3`) hit **`7/7` gates (`88/100`)** with **-20% tokens** (`7.01M`).
   - **Crucial Discovery on Planner Discipline (`C3` vs `R2_C9`/`R2_C7`)**: In `C3`, `kimi-k3.1-pro` grounded its plan in exact file paths, and `deepseek-v4.1-flash` verified the upstream Go `delegatee` fixture schema (`G2=True`, `7/7` gates). In `R2_C9` and `R2_C7`, `mistral-large-4-0` and `qwen3.8-2.4t` wrote plausible-looking covenant specs from memory without reading upstream `delegatee` fixtures, causing Workers to fail `G2` (`58/100` & `54/100`).
   - **Mistral Large 4 (`Mistral-Large-4-1T-A52B`, Mistral Vibe engine) Shone on Security & Token Economy**: Homogeneous `mistral-large-4-0 x4` (`R2_C6`) used only **`1.50M` tokens** and was the **only Round 2 pipeline to pass the live HTTP WebAuthn/IDOR security gate (`G5=True`)**, and in `R2_C7` set `redirect: "error"` (which even Round 1 winners missed!).
   - **Reviewer Prompt Fix Proved Decisive**: Telling `--no-tools` Reviewers explicitly that the diff is inline (`Round 2`) eliminated Round 1's `glm-5.3` tool-announcement no-op — `kimi-k3.1-pro` (`51.8s`), `glm-5.3-prime` (`38.6s`), and `mistral-large-4-0` (`8.3s–102s`) all caught missing `ArkadeExecutorClient.test.js` files and forced Orchestrators to build passing test suites (`R2_C7`, `R2_C8`, `R2_C10`).

### Current #1 Open-Frontier Stack to Beat Closed-Frontier (`95/100`) in Round 3
- **Planner (Read-Only, Grounded)**: `moonshotai/kimi-k3.1-pro` or `mistralai/mistral-large-4-0` *(must verify exact schemas on disk, `<150K` tok, ~60–90s)*
- **Workers (Parallel File-Scoped, like Closed Gold!)**: `deepseek/deepseek-v4.1-flash-1017` *(high-TPS multi-file execution)* + `mistralai/mistral-large-4-0` *(security-critical route/boundary hardening)*
- **Adversarial Diff Reviewer (`--no-tools`, inline diff)**: `moonshotai/kimi-k3.1-pro` or `qwen/qwen3.8-2.4t-a95b` *(catches `:7081`, `redirect: "error"`, empty-hex ScriptNum `0 -> ""`, and CSV bypasses)*
- **Orchestrator / Finisher**: `deepseek/deepseek-v4.1-flash-1017`

---

## Reproducing & Running Next Rounds

```bash
# Run deterministic 7-gate + blind judge evaluation
python3 scripts/eval_blind_round1.py
python3 scripts/eval_blind_round2.py
```
