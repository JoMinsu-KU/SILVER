# Reproducibility Notes

## Package Level

This package is intended for paper review and GitHub release. It contains:

- source scripts used in the Track A-D pipeline,
- aggregate result files used to inspect the reported tables,
- manifests and ledgers needed to trace denominators,
- representative R3 prompt/evidence cases for leakage-boundary inspection,
- representative prompt/evidence examples.

It does not contain the full raw simulator image/log archive for every case. Those artifacts are large and were retained separately during the experiment.

## Path Handling

Some CSV/JSON files preserve original absolute paths such as `C:\SILVER\archive\...`. These are original experiment trace paths. They should be interpreted as artifact identifiers from the run environment, not as required local paths in this repository.

If re-running the scripts, update root paths or environment variables in the scripts to match the new machine.

## Track Data Summary

The included verification script checks the expected high-level denominators:

- Track A manifest: 4,500 samples
- Track B official run: 4,000 rows plus header
- Track C Qwen-guided execution: 2,133 rows plus header
- Track D SR/R3 comparison: 1,040 rows plus header
- Track D ablation subset: 300 rows
- R3 prompt audit: 1,040 prompt files confirmed in the original archive

Run:

```bash
python verify_release_artifacts.py
```

## Security And Privacy

Private SSH keys, actual server IP addresses, and private host setup commands are intentionally excluded. `docs/ENVIRONMENT_TEMPLATE.md` provides the public-safe shape of the runtime.
