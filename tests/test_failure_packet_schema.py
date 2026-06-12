import json
from pathlib import Path

def test_failure_packet_schema_required_fields():
    obj = json.loads((Path(__file__).resolve().parents[1] / 'schemas/failure_packet_schema.json').read_text())
    assert set(obj['required']) == {'sample_id', 'initial_status', 'symptom_log'}
