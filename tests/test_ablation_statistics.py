import csv
from pathlib import Path

def test_ablation_r3_success_count():
    p = Path(__file__).resolve().parents[1] / 'results/main_tables/table_12_ablation_suite_ci.csv'
    with p.open(encoding='utf-8-sig', newline='') as f:
        rows = {r['variant']: r for r in csv.DictReader(f)}
    assert rows['R3']['success'] == '85'
    assert rows['R3_MF']['success'] == '60'
