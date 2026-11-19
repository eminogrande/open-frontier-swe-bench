# Cross-Benchmark Harness Synthesis: `open-frontier-swe-bench` × `pi-durable-swarm`

Cross-referencing our 3-round brownfield monolith benchmark (`nuri-server-musig2-v4-arkade` `#172`, 6.2K LOC) against the controlled 4-harness `Kimi K3.1 Pro` benchmark in `eminogrande/pi-durable-swarm` (`eb803b4`, `ep2` multi-file debug + `ep3` greenfield concurrency spec, blind-judged by `openai/gpt-reserve`).

## Reconciling `ep3` vs Round 3 Results

| Harness | `ep3` Greenfield (`k3.1-pro`) | `ep2` Debug (`31/31`) | Round 3 `#172` Monolith (`k3.1-pro`) | Key Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| **`pi-durable-swarm`** | **`95.33/100`** (`147K` tok, `293s`) | **PASS (`7.3s`)** | *(Testing in Round 4)* | `enableSkills:false`, 4 tools, Verbatim Spec Rule, Same-Module Rule, `onYield` Hard Test Gate |
| **`pi` CLI (`1.5.2`)** | `87.67/100` (**`41.9K` tok**, 6 tools!) | Timeout (`240s`) | `86/100` (`7/7`, **`4.28M` tok**) | `--no-skills` mandatory (`0/100` -> `87.67/100`); `15.5×` fewer tokens than OpenCode |
| **`opencode` (`1.19.3`)** | `91.67/100` (`649.6K` tok) | Timeout (`240s`) | `76/100` (`6/7`, `7.86M` tok) | Highest token overhead (`4.4–15.5×` vs `pi`/`pi-durable`) |
| **`kimi-code` (`2.5.2`)** | `46.00/100` *(missed test file)* | Timeout (`240s`) | **`87/100`** (`7/7`, `6.75M` tok, `884` LOC) | 10.1KB system prompt + 26 tools; `ep3` ran slower `k3.1-pro` (236s single step) vs R3 `k3.1-pro-highspeed` |
| **`dsh` (`0.2.1-rc.5`)** | *(Not in `ep3`)* | *(Not in `ep2`)* | `84/100` solo / **`91/100` guided** | Best guided `deepseek-v4.1-flash` Worker/Finisher; over-explores unguided (`12.7M` tok) |

## Reviewer Audit Findings (`Gemini 4 Neon XHigh`)
1. **Confounders in `ep3` to keep in mind**: `kimi-code` ran `kimi-code/k3.1-pro` (slow endpoint -> 236s single decode) rather than `k3.1-pro-highspeed`, and `pi-durable` was the only harness with `Lead->Coder` + `onYield` auto-retry. Still, the token efficiency (`41.9K`/`147K` vs `649K`) and `onYield` hard-gate advantage (`ep2` sole passer) are decisive.
2. **Two high-leverage upgrades identified for `pi-durable-swarm` (`code.emin.de`)**:
   - `src/daemon.mjs:770`: `onYield` hard test gate globs only `src/*.mjs` + `test/*.test.mjs` — on `.js`/`.ts`/Go/Python repos it silently passes 0 tests (`rc=0`). Auto-detect test runner & fail on 0 executed tests.
   - `src/models.mjs:51-56`: `planner` & `reviewer` still default to `glm-5.3` (`0/100` Planner in R1) and `reviewerDeep` to `deepseek-v4-pro` (`1/100` in R2). Upgrade defaults to **`kimi-k3.1-pro`** (Planner/Reviewer) + **`mistral-large-4-0`** (Security Reviewer) + **`deepseek-v4.1-flash`** (Coder); fix `qwen4-max` label to `API-only`.
3. **3 Harness Laws ported into `open-frontier-swe-bench` Round 4 (`scripts/run_round4_beat_gold.py`)**:
   - **Verbatim Spec Rule**: Planner preserves exact exported names, option keys, file paths, and hashes verbatim.
   - **Same-Module Single-Coder Rule**: Never split a module and its tests across separate workers.
   - **Hard `onYield` Deterministic Test Gate**: Automatically run syntax + `node --test` + regression gate after Worker (up to 2 self-heal retries) *before* Dual Adversarial Review (`kimi-k3.1-pro || mistral-large-4-0`).
