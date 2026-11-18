# Open-Frontier SWE Multi-Agent Benchmark (`open-frontier-swe-bench`)

Empirical, double-blind software-engineering benchmark finding the **best strictly OPEN-FRONTIER model combination** across **Planner -> Worker -> Reviewer -> Orchestrator** — using a **Closed-Frontier Gold PR (`95/100`, `7/7` gates)** solely as the target bar to beat.

Every round is committed to this repository with full raw telemetry, unified `.patch` diffs, anonymized blind-judge mappings, runner harnesses, and model-landscape audits.

---

## Target Bar: Closed-Frontier Reference (`95/100`, `7/7` Gates)

- **Task (`prompts/TASK_PROMPT_arkade_172.md`)**: Server-side slice of `nuri-server-musig2-v4-arkade#172` at frozen commit `136a54faa0c1af817cf9f829412582291a7ec83f` — 4-leaf Tapscript `NuriDelegatedVtxo` artifact (`b9c74e80…`), RFC-8785 JCS SHA-256 `nuri_renew.json` template (`c6d690e1…`), minimal CScriptNum + BIP-68 CSV (`seconds % 512 === 0` & bit-22 `1 << 22`) encoder, `ArkadeExecutorClient.js`, WebAuthn passkey -> MuSig2 `deriveAggregatedPk33` wallet-bound routes (`POST /arkade/executor/delegation/register` & `/status`), anti-IDOR checks, and live HTTP tests.
- **System Skill (`prompts/V3_caveman_adhd_winner.md`)**: Winning `V3` (`CAVEMAN + ADHD MODE`) prompt applied identically across all agents (`-58.6%` token reduction, `100%` gate accuracy in [`agent-prompt-brevity-bench`](https://github.com/eminogrande/agent-prompt-brevity-bench)).
- **Closed-Frontier Reference (`closed_frontier_reference/`)**: Self-orchestrated 3x parallel `google/gemini-4-carbon` workers + `anthropic/claude-fable-5.2` adversarial review (`88/100` v1 -> fixed `redirect: "error"`, route BIP-68 CSV bypass, and config URL log leak -> **`95/100`**, `7/7` deterministic gates). **Excluded from winner selection; exists only as the target to beat.**

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

## Round 1 Results (`rounds/round1/`) — Initial Open Stack (`paymentrequired` Router)

| Rank | Pipeline | Open Weights? | Architecture (`Planner -> Worker -> Reviewer -> Orch`) | Gates (`7`) | Blind Score (`/100`) | Wall (`s`) | Tokens |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| *Ref* | `GOLD_carbon_fable` *(Closed Target)* | No | `3x gemini-4-carbon -> claude-fable-5.2` | **`7/7`** | **`95/100`** | `~190s` | `~145K` |
| **1** | `C6_solo_deepseek_v4_1` | **Yes** | Solo `deepseek-v4.1-flash-abliterated` | **`7/7`** | **`91/100`** | **`380.1s`** | `8,784,093` |
| **2** | `C3_hetero_k3_ds_glm` | **Yes** | `k3.1-pro -> deepseek-v4.1-flash -> glm-5.3 -> deepseek-v4.1-flash` | **`7/7`** | **`88/100`** | `865.4s` | **`7,014,140`** |
| **3** | `C5_hetero_nem_ds_k3` | **Yes** | `nemotron-3-ultra-550b -> deepseek-v4.1-flash -> k3.1-pro -> deepseek-v4.1-flash` | `4/7` | `41/100` | `816.1s` | `4,573,588` |
| **4** | `C2_homo_k3_4stage` | **Yes** | `k3.1-pro x4` (Homogeneous) | `2/7` | `23/100` | `1,401.9s` | `2,266,663` |
| **5** | `C4_hetero_glm_kimi_k3` | **Yes** | `glm-5.3 -> kimi-for-coding -> k3.1-pro -> kimi-for-coding` | `1/7` | `0/100` | `974.8s` | `2,666,593` |
| **6** | `C1_solo_k3_max` | **Yes** | Solo `k3.1-pro` max thinking | `1/7` | `0/100` | `600.1s` | `1,012,631` |

**Round 1 Takeaways:**
- `k3.1-pro` is an elite **Planner** (`199K` tok in `C3`, cutting Worker token burn **-20%** vs Solo `C6`), but times out when used as a monolith **Worker** (`C1`, `C2`).
- Weak Planners poison strong Workers (`nemotron-3-ultra-550b` in `C5` hallucinated opcodes and omitted BIP-68 bit-22, tanking `deepseek-v4.1-flash` from `91 -> 41`).

---

## Round 2 (`rounds/round2/`) — Nov 2026 Expanded Open-Frontier Contenders

See [`research/2026_11_OPEN_FRONTIER_CATALOG.md`](research/2026_11_OPEN_FRONTIER_CATALOG.md) for verified weights/licensing research, including:
- **Mistral Vibe (`mistralai/mistral-vibe`) + Mistral Large 4 (`mistralai/mistral-large-4-0` / HF `Mistral-Large-4-1T-A52B`)** & **Devstral 2 (`mistralai/devstral-2512`)**
- **Qwen3.8 2.4T A95B (`qwen/qwen3.8-2.4t-a95b`, true open-weight flagship)** vs **Qwen4 Max (`qwen/qwen4-max`, released 2026-11-16, currently API-only — tracked as reference)**
- **DeepSeek V4 Pro (`deepseek/deepseek-v4-pro-0813`)** + **DeepSeek V4.1 Flash 1017 (`deepseek/deepseek-v4.1-flash-1017`)**
- **Meta Muse Spark Open (`meta/muse-spark-open` / HF `Muse-Spark-Open-816B-A42B`)**, **Kimi K3.1 Pro (`moonshotai/kimi-k3.1-pro`)**, and **GLM 5.3 Prime (`z-ai/glm-5.3-prime`)**

*(Round 2 execution in progress — full table, patches, and blind Fable judgment committed upon completion.)*
