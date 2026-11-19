# Local Apple M4 (16 GB) Optimization: `DeepSeek-V4-Pro-Qwen3.5-9B` + `harness-hub` LoRA Analysis

Empirical `llama-server` (`0.8.0`, Metal) optimization benchmark on **Apple M4 (16 GB unified memory)** for the installed local model:
- **File**: `~/.local/share/goose/models/deepseek-v4-pro-qwen35-9b-uncensored/DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic.Q4_K_M.gguf` (`5.4 GB`, `qwen35` hybrid DeltaNet/SSM + 8 full-attention layers + embedded `blk.32.nextn.*` MTP speculative head).

## Root Bottlenecks Found in Baseline (`goose-local`)
1. **Embedded MTP head ignored**: `local-server.log` logged `W model has unused tensor blk.32.nextn.* -- ignoring`, leaving decode capped at **`14.6 tok/s`**.
2. **Unbounded `<think>` & multi-turn context bloat**: `--reasoning auto` (`-1` budget) + default `--reasoning-preserve` burned 1,600+ `<think>` tokens on simple coding prompts and re-prefilled prior reasoning traces.
3. **Hybrid-SSM cache & 16 GB RAM traps**: `-np 2 -kvu -ctk q8_0` *slowed* Metal throughput (`15.3 -> 12.7 tok/s`) because `qwen35` only has 8 attention layers (FP16 FA is faster); `-c 65536 -ctxcp 16` caused 37-second macOS swap stalls (`tg_3s` collapsed `22.97 -> 0.55 tok/s`) on 16 GB RAM.
4. **Qwen3.5 repetition loops vs code accuracy**: `temp=0.2` with `presence_penalty=0` looped verbatim comments; `presence_penalty=1.5` broke hex/code tokens; **DRY sampling (`--dry-multiplier 0.5 --dry-allowed-length 4`)** kills loops without penalizing single code tokens.

## Empirical A/B Measurements (`llama-server 0.8.0`, Apple M4 16 GB)

| Config | Flags Delta vs Baseline | Decode (`tok/s`) | Peak `3s` (`tok/s`) | MTP Draft Accepted | RSS / Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| Baseline (`goose-local` old) | `-c 32768 -fa on --jinja --reasoning auto` | `14.6` | `15.5` | `0/0` (ignored) | `111.3s` for 1,600 tok (100% `<think>`) |
| `kvq8 + np2 + kvu` | `-ctk q8_0 -ctv q8_0 -np 2 -kvu -ub 1024` | `12.7–15.2` | — | `0/0` | Slower on hybrid `qwen35` |
| `kvq8 + np2 + draft-mtp` | `+ --spec-type draft-mtp --spec-draft-n-max 4` | `19.3` (`+32%`) | — | `112/122` (`91.8%`) | Dragged by `-np 2`/`q8_0` |
| `clean + draft-mtp(4)` | `-np 1`, FP16 KV, `draft-mtp`, `n-max 4`, `p-min 0.5` | `23.3` (`+60%`) | — | `1,083/1,291` (`83.9%`) | `70.6s` vs `111.3s` |
| `64K + ctxcp 16 + draft-mtp` | `-c 65536 -ctxcp 16` | `12.4` *(swap!)* | `23.4` | — | 37s macOS swap stall (`0.55 tok/s`) |
| **Winner (`SAFE16G_MTP6_DRY`)** | **`-c 32768 -np 1 -ctxcp 4 -cms 4096 --cache-ram 1024 --reasoning-budget 1024 --no-reasoning-preserve --spec-type draft-mtp --spec-draft-n-max 6 --spec-draft-p-min 0.5 --temp 0.3 --dry-multiplier 0.5 --dry-allowed-length 4`** | **`24.6` (`+68.5%`)** | **`29.4` (`2.0×`)** | **`1,216/1,697` (`71.7%`)** | **`6.0 GB` RSS**, zero swap stalls, applied to `~/.local/bin/goose-local` |

## Model Reality Check & Upgrade Paths (`harness-hub` LoRA)
- **Why this 9B model still struggles on hard SWE code**: Upstream model card (`Jackrong/DeepSeek-V4-Pro-Qwen3.5-9B`) confirms it was trained on **~250K Math/STEM samples with zero coding SFT data** (scored `2/11`–`3/11` on Bitcoin `CScriptNum`/`BIP-68` JS unit tests).
- **Best upgrade on Vast.ai GPU (`qwen3.8-27b` at `127.0.0.1:8080`)**: Drop in Hugging Face's **`harness-hub/Qwen3.8-27B-pi-adapted-GGUF`** (`Qwen3.8-27B-pi-lora-F16.gguf`, **320 MB**) via:
  ```bash
  llama-server -m Qwen3.8-27B-Q8_0.gguf --lora Qwen3.8-27B-pi-lora-F16.gguf \
    --chat-template-kwargs '{"enable_thinking": false}' -c 65536 --port 8080 --alias qwen3.8-pi
  ```
  Delivers **`64.7%` SWE-bench Pro** (Hard 51) and **`55.8%` Terminal-Bench 2.1** with **thinking OFF**, **4.5× fewer tokens**, and **55–62% fewer tool calls**.
- **Best 16 GB Apple M4 local coding upgrades** *(once >10 GB SSD is freed; disk currently has `2.3 GB` free)*:
  - `bartowski/MiMo-V2.6-Distill-Qwen-9B-GGUF` (~5.5 GB Q4, 954K downloads, RL-distilled from 1T `MiMo-V2.6-Pro-RL`)
  - `LiquidAI/LFM2.5-24B-A2B-GGUF` + `harness-hub/LFM2.5-24B-A2B-pi-GGUF` (40 MB `pi` RL LoRA, 2B active MoE)
