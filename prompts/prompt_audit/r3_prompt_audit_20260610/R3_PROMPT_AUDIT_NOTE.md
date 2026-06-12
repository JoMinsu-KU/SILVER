# R3 Prompt Leakage Audit Note

작성일: 2026-06-10

## 목적

Track D의 실제 R3 prompt가 논문 본문에서 설명한 정보 경계와 일치하는지 확인했다. 특히 R3가 failure-aware replanning 조건으로서 유효하려면 실패 맥락은 제공하되, official expert plan이나 ground-truth action sequence를 직접 제공하지 않아야 한다.

## 확인한 원격 원본

- 원격 루트: `<EXPERIMENT_ARCHIVE>\silver_track_d_replanning_attribution_20260527`
- R3 prompt 원본 위치: `data\<category>\<task>\exampleXX\replan_R3\prompt_R3.txt`
- 확인된 R3 prompt 수: 1,040개 legacy archive 기준
- 현재 논문 정렬 분모: 2026-06-11 PhysicsLaw replacement 반영 후 1,027개 initial failures
- 비교 CSV: `metrics\track_d_same_plan_vs_replan_R3_all.csv`
- R3 실행 CSV: `metrics\track_d_replan_R3_execution_all_results.csv`

## 전체 스캔 결과

1,040개 legacy `prompt_R3.txt`에 대해 다음 누출 위험 키워드를 스캔했다. 현재 논문 수치는 이 archive에서 PhysicsLaw replacement alignment를 반영한 1,027-case denominator로 보고한다.

- `ground truth`, `GT`
- `operation_sequence`
- `official expert`, `expert sequence`, `expert plan`
- `oracle`
- `correct action`, `next correct`, `gold action`
- `answer key`, `gold sequence`

스캔 결과, 위 표현은 실제 R3 prompt 본문에서 발견되지 않았다.

## 실제 R3 prompt 구조

대표 case 5개를 직접 확인했다. 실제 prompt는 공통적으로 다음 정보를 포함한다.

- public task instruction
- initial Qwen executor plan
- failure observation
- executed trace summary
- allowed JSON output schema

R3 inference 코드는 `prompt_R3.txt` 텍스트와 함께 Track C의 `qwen_guided_execution/final_mosaic.png`를 image input으로 첨부한다. 해당 이미지가 없는 경우에는 `input_mask.png`를 fallback visual evidence로 사용한다.

## 대표 확인 case

| 구분 | sample ID | R3 결과 | SR 결과 | 복사된 증거 |
|---|---|---:|---:|---|
| R3 성공 | `CommenSence/insert_flower_common_sense/example31` | success | fail | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic, initial failure log |
| R3 실패 | `CommenSence/insert_flower_common_sense/example9` | fail | fail | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic, initial failure log |
| R3 entity mapping failure | `CommenSence/select_billiards_common_sense/example3` | C3 | fail | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic, initial failure log |
| R3 conversion failure | `CommenSence/select_billiards_common_sense/example1` | C2 | fail | prompt, raw/parsed output, adapter validation, executor plan |
| SR success / R3 fail | `CommenSence/insert_flower_common_sense/example81` | fail | success | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic, initial failure log |

## 판단

현재 확보한 실제 R3 prompt와 코드 경로는 논문 본문의 핵심 설명과 대체로 일치한다.

- R3는 단순 재시도가 아니라 기존 실패 plan을 다시 계획하도록 유도한다.
- 실패 관찰 정보와 stage-level trace summary는 포함된다.
- official expert operation sequence, expert action order, direct next correct action은 prompt에 포함되지 않는다.
- final failure image는 prompt text 파일에 쓰이는 것이 아니라 OpenAI-compatible multimodal message의 image input으로 첨부된다.

주의할 점은 `Initial Qwen executor plan` 안에 scene entity의 name, component id, position, xml path 등이 포함된다는 것이다. 이는 Track C 실행을 위해 생성된 Qwen-derived executor plan과 entity registry 기반 정보이며, official expert answer를 직접 제공하는 것은 아니다. 다만 appendix에서는 이 점을 명확히 설명하는 것이 좋다.

## 로컬 보관 위치

대표 case 증거는 이 폴더 아래 case별 하위 폴더에 보관했다.

- `prompt_R3.txt`
- `raw_output.json`
- `parsed_output.json`
- `adapter_validation.json`
- `executor_plan.json`
- `entity_registry.json`
- 가능한 경우 `failure_final_mosaic.png`
- 가능한 경우 `initial_failure_execution_result.json`
- 가능한 경우 `initial_failure_orchestrator.log`
