# Prompt Leakage Audit

Representative real R3 prompts are stored in `prompts/prompt_audit/`. The audit boundary is:

- Allowed: original instruction, failed Qwen plan context, adapter-resolved metadata for Qwen-selected entities, bounded symptom diagnosis, final failure image reference.
- Disallowed: official expert sequence, corrected object name, direct next action, ground-truth target.

The provided prompt examples should be inspected together with `examples/r3_prompt_audit_20260610/R3_PROMPT_AUDIT_NOTE.md`.
