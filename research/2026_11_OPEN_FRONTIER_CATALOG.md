# Nov 2026 Open-Frontier Coding & Reasoning Model Catalog

Verified live against Hugging Face Hub (`huggingface.co/api/models`), OpenRouter (`openrouter.ai/api/v1/models`), GitHub (`mistralai/mistral-vibe`), and live CLI agent execution (`pi` tool-calling harness) on **2026-11-18**.

## Critical Naming & Open-Weights Clarifications

1. **"Mistral Vibe Code Large" = `mistralai/mistral-vibe` (CLI Agent) + `mistralai/mistral-large-4-0` (`Mistral-Large-4-1T-A52B`)**:
   - **`mistralai/mistral-vibe`** (`https://github.com/mistralai/mistral-vibe`, Apache-2.0, 5.4K stars) is Mistral's open-source terminal coding agent CLI (`vibe`).
   - Its flagship open-weight engine is **Mistral Large 4** (`mistralai/mistral-large-4-0` / HF `mistralai/Mistral-Large-4-1T-A52B`, released Oct/Nov 2026, **1T total / 52B active MoE**, 1M context, native reasoning `low`/`medium`/`high`), alongside Mistral's smaller dense coding model **Devstral 2** (`mistralai/devstral-2512` / HF `mistralai/Devstral-2-123B-Instruct-2512`, 123B dense, 256K context).
2. **`qwen/qwen4-max` vs `qwen/qwen3.8-2.4t-a95b` (API-Proprietary vs True Open-Weight Flagship)**:
   - **`qwen/qwen4-max`** (released **2026-11-16**, 1M context, native reasoning) is Alibaba's brand-new Qwen4 flagship SKU, **currently API-only (`hugging_face_id: null`)** — Alibaba has not yet released open weights for Qwen4 Max on Hugging Face.
   - **`qwen/qwen3.8-2.4t-a95b`** (HF `Qwen/Qwen3.8-2.4T-A95B`, updated **2026-11-07**, **2.4T total / 95B active MoE**, 1M context, `86.6%` Terminal Bench 2.1, `73.5%` FrontierSWE) is Qwen's largest **downloadable open-weight** flagship. Both are benchmarked head-to-head in Round 2 so you see exact open-weight vs API-flagship numbers.
3. **`meta/muse-spark-open` (`meta-models/Muse-Spark-Open-816B-A42B`)**:
   - Meta's coding-specialized open-weight MoE (**816B total / 42B active**, 1M context, Oct 2026). Note: in `pi`'s generic OpenAI-completions multi-turn harness, `muse-spark-open` exhibited a 1-turn text-announcement quirk ("Implementing...") without invoking tools when unguided (`R2_C4`), which our Round 2 telemetry captures empirically.

## Verified Nov 2026 Open-Weight SWE Contenders

| Model ID | Hugging Face Weights | Params (Total / Active) | Context | Released / Updated | True Open Weights? | Role Sweet Spot |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `mistralai/mistral-large-4-0` | `mistralai/Mistral-Large-4-1T-A52B` | 1T / 52B MoE | 1M | 2026-10 / 11 | **Yes** | Planner, Worker, Reviewer (Mistral Vibe engine; -47% token burn) |
| `qwen/qwen3.8-2.4t-a95b` | `Qwen/Qwen3.8-2.4T-A95B` | 2.4T / 95B MoE | 1M | 2026-11-07 | **Yes** | Frontier Planner, Solo Agent, Adversarial Reviewer |
| `qwen/qwen4-max` | *(None yet — API SKU)* | Undisclosed | 1M | 2026-11-16 | **No (API-only)** | Tracked as Qwen4 reference until open weights drop |
| `moonshotai/kimi-k3.1-pro` | `moonshotai/Kimi-K3.1-Pro` | ~2.8T MoE | 1M | 2026-10-23 | **Yes** | **Top Planner & Diff Reviewer** (too slow as monolith Worker) |
| `deepseek/deepseek-v4-pro-0813` | `deepseek-ai/DeepSeek-V4-Pro-0813` | 1.6T MoE | 1M | 2026-08-13 | **Yes** | Deep Reasoning Planner / Solo Flagship |
| `deepseek/deepseek-v4.1-flash-1017` | `deepseek-ai/DeepSeek-V4.1-Flash-1017` | ~284B / 13B+ MoE | 1M | 2026-10-17 | **Yes** | **High-TPS Worker & Orchestrator** |
| `meta/muse-spark-open` | `meta-models/Muse-Spark-Open-816B-A42B` | 816B / 42B MoE | 1M | 2026-10-15 | **Yes** | Coding specialist (requires strict tool-forcing harness) |
| `mistralai/devstral-2512` | `mistralai/Devstral-2-123B-Instruct-2512` | 123B Dense | 256K | 2025-12-09 | **Yes** | Fast non-reasoning SWE Worker |
| `z-ai/glm-5.3` / `glm-5.3-prime` | `zai-org/GLM-5.3` | Frontier MoE | 1M | 2026-09 / 10 | **Yes** | Fast Planner / Reviewer |
| `minimax/minimax-m3.1-flash` | `MiniMaxAI/MiniMax-M3.1-Flash` | MoE | 1M | 2026-10-19 | **Yes** | Fast cybersecurity/agentic Worker |
| `tencent/hy4` / `hy4-flash` | `tencent/Hy4` / `tencent/Hy4-flash` | 700B+ / 49B MoE | 1M | 2026-11-04 / 16 | **Yes** | Long-horizon agentic candidate (Round 3+) |
