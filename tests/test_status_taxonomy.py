import json
from pathlib import Path

def test_status_codes_exist():
    obj = json.loads((Path(__file__).resolve().parents[1] / 'schemas/status_codes.json').read_text())
    assert 'C0_qwen_guided_success' in obj['C']
    assert 'C3_entity_mapping_failure' in obj['C']
