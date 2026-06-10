# Track B Evidence Audit Report

## 목적

Track B 최종 결과 4,000개에 대해 per-case evidence가 실제로 남아 있는지 확인했다. 검사 대상은 case directory, final attempt의 `execution_result.json`, `orchestrator.log`, completed attempt의 camera image/mosaic이다.

## 감사 결과 요약

- results rows: 4000
- unique sample indices: 4000
- case directories: 4000
- execution_result.json files: 9071
- orchestrator.log files: 9083
- initial mosaic files: 7481
- final mosaic files: 7473
- total PNG files: 74850
- rows with missing evidence: 0
- missing file counts: `{}`

## 해석

최신 evidence audit 기준으로 Track B의 evidence 누락은 0개다. 따라서 `B0_official_eligible` main denominator뿐 아니라 `B1/B3/B4/B5` diagnostic set도 모두 최소한의 case-level evidence를 가진다.

완료된 native execution attempt에는 camera image/mosaic가 남아 있으며, crash/timeout/exception attempt에는 `execution_result.json`과 `orchestrator.log`가 남아 있다. timeout attempt는 정상적으로 이미지가 없을 수 있으므로, image 부재를 evidence 누락으로 간주하지 않는다.

## 경로 처리 메모

일부 retry directory는 Windows classic path 길이 제한에 가까워 일반 Python `Path.exists()`가 파일을 찾지 못하는 문제가 있었다. Audit 스크립트를 `\\?\` extended-length path 방식으로 수정한 뒤 재감사했으며, 그 결과 missing evidence는 0개로 확인되었다.

## Evidence files

- summary JSON: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\evidence_audit\track_b_evidence_audit_summary.json`
- per-sample CSV: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\evidence_audit\track_b_evidence_audit_per_sample.csv`
- missing evidence target list: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\evidence_audit\missing_evidence_cases.jsonl`
- missing evidence rerun report: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\evidence_audit\TRACK_B_MISSING_EVIDENCE_RERUN_REPORT.md`
