# Track C 상세 분석: Qwen-Guided Execution 결과(C0-C4)

작성 시각: 2026-05-27

## 1. 분석 기준

본 문서는 `Track B official expert eligibility`를 통과한 2,133개 sample에 대해 Qwen P2 planning 결과를 VLABench official expert/task template에 주입해 실행한 Track C 결과를 정리한다.

집계는 저장된 artifact와 2026-06-11 PhysicsLaw replacement summary를 사용했다.

- 원본 결과 CSV: `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\qwen_guided_execution_results.csv`
- 정렬 결과 CSV: `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260611_physicslaw_replaced\metrics\qwen_guided_execution_results_physicslaw_replaced.csv`
- case별 증거 폴더: `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\data\<category>\<task>\<example>`
- 필수 증거: `entity_registry.json`, `qwen_p2_adapter_validation.json`, `qwen_p2_executor_plan.json`, `qwen_guided_execution/execution_result.json`, `initial_mosaic.png`, `final_mosaic.png`, `orchestrator.log`

최종 집계에서 native exception 잔여 case는 없다. 따라서 본문 분석은 C0-C4만 사용한다.

## 2. 전체 결과 요약

- 전체 대상: 2133개
- 성공: 1106개
- 전체 기준 성공률: 51.85%
- 실제 native 실행 완료 case: 1907개
- native 실행 완료 기준 성공률: 58.00%
- Qwen plan 변환 성공: 1925개 / 2133개 = 90.25%
- Qwen plan 변환 실패: 208개 / 2133개 = 9.75%

| 상태 | 의미 | 개수 | 전체 대비 |
| --- | --- | --- | --- |
| C0_qwen_guided_success | 성공 | 1106 | 51.85% |
| C1_qwen_guided_condition_failure | 실행은 됐지만 목표 조건 실패 | 819 | 38.40% |
| C2_qwen_conversion_failure | 실행 가능한 Qwen plan 변환 실패 | 168 | 7.88% |
| C3_entity_mapping_failure | Qwen entity가 scene registry와 매핑 실패 | 39 | 1.83% |
| C4_unsupported_qwen_skill | 지원하지 않는 skill 제안 | 1 | 0.05% |

## 3. 상태별 해석

### C0: Qwen-guided execution success

Qwen이 선택한 skill sequence와 object/target이 scene registry에 매핑됐고, VLABench official execution 결과 task condition까지 만족한 경우다. 이 값은 Track C의 main success로 사용한다.

### C1: Qwen-guided condition failure

실행 자체는 완료됐지만 task condition을 만족하지 못한 경우다. 이 상태는 executor crash가 아니라 Qwen-guided plan의 목표 선택, 순서, target grounding, 또는 task condition alignment가 충분하지 않았다는 의미다. 특히 `progress_score`가 0.5인 case는 일부 stage는 수행됐으나 최종 목표가 틀린 경우로 해석할 수 있다.

| progress_score | 개수 | C1 내부 비율 |
| --- | --- | --- |
| 0.0 | 85 | 10.76% |
| 0.3333333333333333 | 189 | 23.92% |
| 0.5 | 515 | 65.19% |
| 0.6666666666666666 | 1 | 0.13% |

### C2: Qwen conversion failure

Qwen 출력이 실행 가능한 symbolic plan으로 변환되지 않은 경우다. 대표적으로 `skill_sequence`가 비어 있거나 JSON 구조상 실행 가능한 action이 없는 경우다. 이 상태는 실행기가 실패한 것이 아니라, 모델이 실행 가능한 plan을 생성하지 못한 실패로 분류한다.

| 변환 실패 사유 | 개수 | C2 내부 비율 |
| --- | --- | --- |
| sequence_missing_or_empty | 168 | 100.00% |

C2가 많이 발생한 task는 다음과 같다.

| Category | Task | C2 개수 |
| --- | --- | --- |
| M&T | select_poker | 72 |
| Semantic | select_poker_semantic | 25 |
| CommenSence | select_nth_largest_poker | 23 |
| M&T | select_billiards | 22 |
| CommenSence | select_billiards_common_sense | 11 |
| Semantic | select_toy_semantic | 5 |
| Semantic | select_drink_semantic | 3 |
| Semantic | select_book_semantic | 2 |
| Semantic | select_fruit_semantic | 2 |
| Spatial | select_poker_spatial | 2 |
| M&T | select_book | 1 |

### C3: entity mapping failure

Qwen 출력에 skill/action 구조는 있으나, object 또는 target 표현이 VLABench scene registry의 실제 entity와 연결되지 않은 경우다. 이 상태는 plan schema 자체보다 object naming, spatial reference, visual grounding에서 문제가 발생한 것으로 해석한다.

| Category | Task | C3 개수 |
| --- | --- | --- |
| Spatial | select_billiards_spatial | 36 |
| M&T | select_billiards | 2 |
| Spatial | select_toy_spatial | 1 |

### C4: unsupported Qwen skill

Qwen이 현재 Track C adapter가 허용한 skill set 밖의 action을 제안한 경우다. 1건만 관측됐으므로 전체 결과에 미치는 양적 영향은 작지만, replanning 단계에서는 unsupported action 억제 prompt가 필요하다.

## 4. Category별 결과

| Category | 대상 | 성공 | 성공률 | C1 | C2 | C3 | C4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CommenSence | 519 | 311 | 59.92% | 174 | 34 | 0 | 0 |
| M&T | 616 | 326 | 52.92% | 193 | 95 | 2 | 0 |
| PhysicsLaw | 42 | 13 | 30.95% | 29 | 0 | 0 | 0 |
| Semantic | 507 | 342 | 67.46% | 127 | 37 | 0 | 1 |
| Spatial | 449 | 114 | 25.39% | 296 | 2 | 37 | 0 |

해석상 중요한 점은 category별 편차가 크다는 것이다. toy, fruit, chemistry tube처럼 시각적 구분이 비교적 명확한 task는 높은 성공률을 보였고, poker/billiards/spatial 계열은 낮았다. 이는 Qwen의 전체 planning 능력 하나만으로 설명하기 어렵고, 작은 시각 기호, 유사 객체 간 구분, 공간 관계 grounding이 결합된 난이도 차이로 보는 것이 적절하다.

## 5. Task별 고성공/저성공 구간

### 성공률 상위 task

| Category | Task | 대상 | 성공 | 성공률 | C1 | C2 | C3 | C4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Semantic | select_fruit_semantic | 97 | 91 | 93.81% | 4 | 2 | 0 | 0 |
| CommenSence | select_toy_common_sense | 74 | 69 | 93.24% | 5 | 0 | 0 | 0 |
| Semantic | select_chemistry_tube_semantic | 94 | 85 | 90.43% | 9 | 0 | 0 | 0 |
| M&T | select_toy | 76 | 68 | 89.47% | 8 | 0 | 0 | 0 |
| Semantic | select_toy_semantic | 72 | 63 | 87.50% | 4 | 5 | 0 | 0 |
| CommenSence | select_chemistry_tube_common_sense | 84 | 72 | 85.71% | 12 | 0 | 0 | 0 |
| M&T | select_chemistry_tube | 94 | 77 | 81.91% | 17 | 0 | 0 | 0 |
| CommenSence | select_fruit_common_sense | 97 | 74 | 76.29% | 23 | 0 | 0 | 0 |
| CommenSence | insert_flower_common_sense | 27 | 20 | 74.07% | 7 | 0 | 0 | 0 |
| Semantic | insert_flower_semantic | 26 | 19 | 73.08% | 7 | 0 | 0 | 0 |

### 성공률 하위 task

| Category | Task | 대상 | 성공 | 성공률 | C1 | C2 | C3 | C4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Spatial | select_billiards_spatial | 60 | 0 | 0.00% | 24 | 0 | 36 | 0 |
| PhysicsLaw | thermal_expansion_qa | 7 | 0 | 0.00% | 7 | 0 | 0 | 0 |
| PhysicsLaw | speed_of_sound_qa | 11 | 2 | 18.18% | 9 | 0 | 0 | 0 |
| PhysicsLaw | friction_qa | 9 | 2 | 22.22% | 7 | 0 | 0 | 0 |
| PhysicsLaw | magnetism_qa | 6 | 3 | 50.00% | 3 | 0 | 0 | 0 |
| PhysicsLaw | density_qa | 9 | 6 | 66.67% | 3 | 0 | 0 | 0 |
| M&T | add_condiment | 1 | 0 | 0.00% | 1 | 0 | 0 | 0 |
| M&T | select_poker | 100 | 7 | 7.00% | 21 | 72 | 0 | 0 |
| M&T | select_billiards | 100 | 14 | 14.00% | 62 | 22 | 2 | 0 |
| Spatial | select_toy_spatial | 84 | 12 | 14.29% | 71 | 0 | 1 | 0 |

저성공 task는 크게 세 부류로 나뉜다.

1. 카드/당구공처럼 작은 숫자, 무늬, 색상, 순서를 읽어야 하는 visual-symbol grounding 문제
2. spatial relation을 정확히 해석해야 하는 공간 grounding 문제
3. QA 계열처럼 조작 실행 primitive로 바로 환원하기 어려운 task-interface alignment 문제

## 6. 논문 해석 포인트

Track C의 핵심 결과는 Qwen이 단순히 JSON을 출력하는 수준을 넘어 실제 VLABench official execution으로 연결됐을 때 약 절반 수준의 성공률을 보였다는 점이다. 이는 Track A의 planning-only score만으로는 실제 실행 가능성을 충분히 설명할 수 없다는 근거가 된다.

특히 C1과 C2의 분리가 중요하다.

- C1은 “그럴듯한 plan은 있고 실행도 됐지만 최종 목표가 틀린” 실패다.
- C2는 “실행 가능한 plan 자체를 만들지 못한” 실패다.
- C3는 “계획 구조는 있으나 scene entity grounding에 실패한” 실패다.

이 구분은 SILVER의 failure-aware replanning 필요성을 뒷받침한다. Track D에서는 C1/C2/C3를 동일한 실패로 뭉개지 말고, 실패 유형별로 recovery 가능성을 분리해서 평가해야 한다.

## 7. Track D로 넘길 대상 정의

Track D의 primary set은 다음 조건으로 구성하는 것이 적절하다.

- Track B eligible sample
- Track C에서 C1, C2, C3, C4로 실패한 case
- 동일 plan retry와 SILVER replan을 paired design으로 비교

다만 C2는 실행 로그가 없거나 `not_run_conversion_failed`이므로, replan prompt에는 initial execution failure가 아니라 “conversion failure / empty plan / invalid plan” 증상을 제공해야 한다. C1은 final visual evidence와 stage log를 제공할 수 있으므로 failure-aware replanning의 핵심 대상이다. C3는 entity mapping 실패를 명시적으로 제공하되 GT object/target을 직접 제공하면 안 된다.

## 8. 산출물

추가로 생성한 분석 파일은 다음과 같다.

- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c0_c4_status_summary.csv`
- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c0_c4_by_category.csv`
- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c0_c4_by_task.csv`
- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c2_error_breakdown.csv`
- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c2_by_task.csv`
- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c3_by_task.csv`
- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c4_examples.csv`
- `<EXPERIMENT_ARCHIVE>\silver_track_c_qwen_guided_20260524\metrics\track_c_c1_progress_distribution.csv`

## 9. 결론

Track C는 PhysicsLaw replacement 반영 후 전체 2,133개 대상에서 1,106개 성공, 1,027개 실패로 정리된다. 실패의 대부분은 native 실행 문제가 아니라 Qwen의 condition-level 목표 실패(C1), 실행 가능한 plan 생성 실패(C2), scene entity grounding 실패(C3)로 구분된다. 따라서 다음 단계인 Track D는 단순 성공률 향상이 아니라, 이 실패 유형 중 어떤 유형이 failure-aware replanning으로 회복 가능한지를 측정하는 방향으로 진행해야 한다.
