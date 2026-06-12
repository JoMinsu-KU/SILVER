# SILVER

Supplementary reproducibility package for:

**Failure-Aware Replanning Evaluation for Vision-Language-Model-Guided Robotic Manipulation in Simulator-in-the-Loop Environments**

SILVER stands for **Simulator-in-the-Loop Verification and Evaluation of Replanning**.

This repository provides the public ledgers, aggregate tables, schemas, prompt templates, representative prompt-audit evidence, and recomputation scripts used to support the paper. It is a supplementary release package, not a redistribution of VLABench raw assets or a complete simulator archive.

## Repository Structure

```text
configs/      Experiment configuration summaries.
data/         Sample IDs, per-sample records, breakdowns, and checksums.
docs/         Data dictionary, leakage audit notes, taxonomy definitions, and reproducibility notes.
prompts/      Planning/replanning prompt templates and representative real R3 prompt audit examples.
results/      Paper-facing main and supplementary CSV tables.
schemas/      Output, failure-packet, adapter-validation, and status-code schemas.
src/silver/   Reusable SILVER method-level API and executor-adapter code.
scripts/      Verification and table recomputation scripts.
tests/        Lightweight consistency tests for released artifacts.
```

## Main Denominators

- Track A public planning samples: 4,500.
- Track B S0 execution-candidate samples: 4,000.
- Track B official-expert-eligible samples: 2,133.
- Track C initial Qwen-guided successes: 1,106.
- Track D initial failures for paired recovery: 1,027.
- Track D same-plan retry recoveries: 36.
- Track D SILVER-R3 recoveries: 326.

## Quick Verification

```bash
python verify_release_artifacts.py
python scripts/recompute_all_tables.py
```

## Scope

The package intentionally excludes draft manuscript files, raw simulator image/log archives, private machine paths, SSH keys, model weights, and upstream VLABench assets. Representative real R3 prompts are included under `prompts/prompt_audit/` for leakage-boundary inspection.

## Citation

See `CITATION.cff`.
