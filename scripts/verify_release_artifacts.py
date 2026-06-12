from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'data/sample_ids/stage1_public_4500_ids.csv',
    'data/sample_ids/stage2_execution_candidate_4000_ids.csv',
    'data/sample_ids/stage2_official_expert_eligible_2133_ids.csv',
    'data/sample_ids/stage3_initial_failures_1027_ids.csv',
    'data/records/stage4_sr_r3_paired_records.csv',
    'results/main_tables/table_10_stage4_paired_recovery.csv',
    'prompts/prompt_audit/r3_prompt_audit_20260610/R3_PROMPT_AUDIT_NOTE.md',
    'schemas/status_codes.json',
]

EXPECTED_ROWS = {
    'data/sample_ids/stage1_public_4500_ids.csv': 4500,
    'data/sample_ids/stage2_execution_candidate_4000_ids.csv': 4000,
    'data/sample_ids/stage2_official_expert_eligible_2133_ids.csv': 2133,
    'data/sample_ids/stage3_initial_failures_1027_ids.csv': 1027,
    'data/records/stage4_sr_r3_paired_records.csv': 1027,
}

def count_csv(path: Path) -> int:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return sum(1 for _ in csv.DictReader(f))

def main() -> int:
    errors = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append(f'missing: {rel}')
    for rel, expected in EXPECTED_ROWS.items():
        path = ROOT / rel
        if path.exists():
            got = count_csv(path)
            if got != expected:
                errors.append(f'row_count_mismatch: {rel} expected={expected} got={got}')
    if errors:
        print(json.dumps({'ok': False, 'errors': errors}, indent=2))
        return 1
    print(json.dumps({'ok': True, 'checked_files': len(REQUIRED)}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
