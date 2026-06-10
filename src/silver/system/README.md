# SILVER System Code

This folder contains the reusable method-level code for SILVER, separated from
the Track A-D experiment runners.

## Components

- `failure_packet.py`: creates bounded textual failure packets from Track C/D execution artifacts.
- `prompt_builder.py`: builds the R3 failure-aware replanning prompt.
- `schema.py`: defines the supported high-level skill/output schema.
- `client.py`: builds multimodal OpenAI-compatible messages and calls `/chat/completions`.
- `result_parser.py`: extracts and validates structured JSON responses.
- `executor_adapter.py`: exposes the VLABench SkillLib-compatible executor-plan adapter used in the experiments.
- `attribution.py`: computes same-plan retry vs SILVER recovery attribution labels and recovery gain.
- `pipeline.py`: provides a minimal R3 replanner API that connects prompt, client, parser, and executor adapter.

## Information Boundary

The R3 prompt includes:

- public task instruction,
- failed Qwen-derived executor plan,
- bounded failure observation,
- compact execution trace summary,
- allowed output schema.

The R3 prompt excludes:

- official expert operation sequence,
- official expert action order,
- corrected object/target labels,
- direct next-correct-action hints.

The failure/final image is attached as a multimodal input by `client.py`; it is
not embedded as text inside `prompt_R3.txt`.
