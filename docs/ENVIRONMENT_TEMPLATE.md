# Public Environment Template

This document describes the environment shape used for the SILVER experiments without exposing private hostnames, IP addresses, SSH keys, or local account names.

## Simulator Runtime

- OS: Windows host with WSL for VLABench/MuJoCo execution
- Python: 3.10 for VLABench runtime
- Main packages:
  - VLABench
  - MuJoCo
  - dm_control
  - numpy
  - pandas
  - requests
  - Pillow

## VLM Serving Runtime

- Model: `Qwen/Qwen3-VL-8B-Instruct`
- Server type: OpenAI-compatible endpoint
- Endpoint shape:

```text
http://127.0.0.1:8000/v1/chat/completions
```

- Decoding:
  - `temperature = 0`
  - `max_tokens = 1024` for replanning runs

## Model Server Example

The exact host and SSH key details are intentionally omitted. A typical setup is:

```bash
vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype bfloat16 \
  --max-model-len 8192 \
  --limit-mm-per-prompt '{"image":4}'
```

If the model server runs on a separate machine, expose it to the experiment machine with an SSH tunnel:

```bash
ssh -N -L 8000:127.0.0.1:8000 <user>@<model-server-host>
```

Then verify:

```bash
curl http://127.0.0.1:8000/v1/models
```

## Reproduction Notes

The released package contains aggregate artifacts. Re-running the full native simulator evaluation requires local VLABench assets and a compatible MuJoCo rendering setup. The full raw image/log archive is not included in the GitHub-sized package.

