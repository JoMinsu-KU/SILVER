import csv
from pathlib import Path

def test_stage4_record_count():
    p = Path(__file__).resolve().parents[1] / 'data/records/stage4_sr_r3_paired_records.csv'
    with p.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1027
    assert sum(r['r3_success'] == 'True' for r in rows) == 326
