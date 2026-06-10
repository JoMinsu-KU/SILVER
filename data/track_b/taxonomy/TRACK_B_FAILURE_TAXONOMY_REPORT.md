# Track B Failure Taxonomy Report

## 1. 목적

이 문서는 Track B official expert eligibility 결과를 논문 작성에 사용할 수 있는 failure taxonomy 형태로 재구성한 최종 분석 보고서다. 모든 수치는 저장된 `official_results.csv`, `summary_by_task.csv`, `official_summary.json`, evidence audit artifact에서 재계산했으며 mock 결과를 포함하지 않는다.

Track B taxonomy의 핵심 목적은 VLM planning failure와 native execution eligibility failure를 분리하는 것이다. 따라서 Track C/D의 main denominator는 `XB0`만 사용하고, `XB1-XB4`는 diagnostic set으로 유지한다.

## 2. Taxonomy 정의

| 기존 label | Taxonomy | 한국어 명칭 | main/diagnostic | 의미 |
| --- | --- | --- | --- | --- |
| `B0_official_eligible` | `XB0: Execution-ready` | 실행 준비 완료 | Track C/D main denominator | official expert 2회 모두 성공한 sample |
| `B1_condition_failure` | `XB1: Completed-but-condition-failed` | 완료됐지만 성공 조건 실패 | Diagnostic set | native 실행은 완료됐지만 task success condition을 만족하지 못한 sample |
| `B3_native_exception` | `XB2: Native-exception failure` | native 예외/크래시 | Diagnostic set | VLABench/dm_control/SkillLib/native layer에서 exception 또는 crash가 발생한 sample |
| `B4_timeout` | `XB3: Native-timeout failure` | native timeout | Diagnostic set | 300초 제한 내 official expert 실행이 완료되지 못한 sample |
| `B5_nondeterministic_mismatch` | `XB4: Non-deterministic eligibility` | 반복 실행 비결정성 | Diagnostic set | 동일 sample의 1회차와 2회차 결과가 일치하지 않은 sample |

## 3. 전체 taxonomy 결과

| Taxonomy | 개수 | 전체 대비 비율 | 해석 |
| --- | --- | --- | --- |
| `XB0` 실행 준비 완료 | 2133 / 4000 | 53.33% | official expert 2회 모두 성공한 sample |
| `XB1` 조건 실패 | 1217 / 4000 | 30.43% | 실행은 완료됐지만 task success condition을 만족하지 못한 sample |
| `XB2` native 예외/크래시 | 214 / 4000 | 5.35% | native layer에서 exception 또는 crash가 발생한 sample |
| `XB3` native timeout | 57 / 4000 | 1.43% | 300초 제한 내 official expert 실행이 완료되지 못한 sample |
| `XB4` 반복 실행 비결정성 | 379 / 4000 | 9.47% | 동일 sample의 1회차와 2회차 결과가 불일치한 sample |

Track C/D main denominator는 `XB0` 2133개이다. Diagnostic set은 1867개이다.

## 4. 카테고리별 taxonomy 분포

| 카테고리 | 전체 | XB0 실행 준비 완료 | XB1 조건 실패 | XB2 native 예외 | XB3 timeout | XB4 비결정성 | XB0 비율 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CommenSence | 800 | 519 | 213 | 13 | 2 | 53 | 64.88% |
| M&T | 900 | 616 | 222 | 1 | 0 | 61 | 68.44% |
| PhysicsLaw | 600 | 42 | 296 | 100 | 0 | 162 | 7.00% |
| Semantic | 900 | 507 | 228 | 100 | 1 | 64 | 56.33% |
| Spatial | 800 | 449 | 258 | 0 | 54 | 39 | 56.12% |

## 5. Task별 taxonomy 분포

| 카테고리 | Task | 전체 | XB0 | XB1 | XB2 | XB3 | XB4 | XB0 비율 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CommenSence | `add_condiment_common_sense` | 100 | 0 | 94 | 0 | 0 | 6 | 0.00% |
| CommenSence | `insert_flower_common_sense` | 100 | 27 | 57 | 4 | 0 | 12 | 27.00% |
| CommenSence | `select_billiards_common_sense` | 100 | 97 | 0 | 1 | 2 | 0 | 97.00% |
| CommenSence | `select_chemistry_tube_common_sense` | 100 | 84 | 3 | 8 | 0 | 5 | 84.00% |
| CommenSence | `select_drink_common_sense` | 100 | 41 | 37 | 0 | 0 | 22 | 41.00% |
| CommenSence | `select_fruit_common_sense` | 100 | 97 | 1 | 0 | 0 | 2 | 97.00% |
| CommenSence | `select_nth_largest_poker` | 100 | 99 | 1 | 0 | 0 | 0 | 99.00% |
| CommenSence | `select_toy_common_sense` | 100 | 74 | 20 | 0 | 0 | 6 | 74.00% |
| M&T | `add_condiment` | 100 | 1 | 97 | 0 | 0 | 2 | 1.00% |
| M&T | `insert_flower` | 100 | 31 | 52 | 1 | 0 | 16 | 31.00% |
| M&T | `select_billiards` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| M&T | `select_book` | 100 | 73 | 5 | 0 | 0 | 22 | 73.00% |
| M&T | `select_chemistry_tube` | 100 | 94 | 4 | 0 | 0 | 2 | 94.00% |
| M&T | `select_drink` | 100 | 44 | 43 | 0 | 0 | 13 | 44.00% |
| M&T | `select_fruit` | 100 | 97 | 1 | 0 | 0 | 2 | 97.00% |
| M&T | `select_poker` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| M&T | `select_toy` | 100 | 76 | 20 | 0 | 0 | 4 | 76.00% |
| PhysicsLaw | `density_qa` | 100 | 9 | 61 | 0 | 0 | 30 | 9.00% |
| PhysicsLaw | `friction_qa` | 100 | 9 | 62 | 0 | 0 | 29 | 9.00% |
| PhysicsLaw | `magnetism_qa` | 100 | 6 | 57 | 0 | 0 | 37 | 6.00% |
| PhysicsLaw | `reflection_qa` | 100 | 0 | 0 | 100 | 0 | 0 | 0.00% |
| PhysicsLaw | `speed_of_sound_qa` | 100 | 11 | 56 | 0 | 0 | 33 | 11.00% |
| PhysicsLaw | `thermal_expansion_qa` | 100 | 7 | 60 | 0 | 0 | 33 | 7.00% |
| Semantic | `add_condiment_semantic` | 100 | 0 | 98 | 0 | 0 | 2 | 0.00% |
| Semantic | `insert_flower_semantic` | 100 | 26 | 53 | 0 | 0 | 21 | 26.00% |
| Semantic | `select_billiards_semantic` | 100 | 0 | 0 | 100 | 0 | 0 | 0.00% |
| Semantic | `select_book_semantic` | 100 | 78 | 6 | 0 | 0 | 16 | 78.00% |
| Semantic | `select_chemistry_tube_semantic` | 100 | 94 | 4 | 0 | 1 | 1 | 94.00% |
| Semantic | `select_drink_semantic` | 100 | 40 | 45 | 0 | 0 | 15 | 40.00% |
| Semantic | `select_fruit_semantic` | 100 | 97 | 1 | 0 | 0 | 2 | 97.00% |
| Semantic | `select_poker_semantic` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| Semantic | `select_toy_semantic` | 100 | 72 | 21 | 0 | 0 | 7 | 72.00% |
| Spatial | `add_condiment_spatial` | 100 | 0 | 99 | 0 | 0 | 1 | 0.00% |
| Spatial | `insert_bloom_flower` | 100 | 28 | 60 | 0 | 0 | 12 | 28.00% |
| Spatial | `select_billiards_spatial` | 100 | 60 | 36 | 0 | 0 | 4 | 60.00% |
| Spatial | `select_book_spatial` | 100 | 85 | 2 | 0 | 0 | 13 | 85.00% |
| Spatial | `select_chemistry_tube_spatial` | 100 | 92 | 4 | 0 | 0 | 4 | 92.00% |
| Spatial | `select_fruit_spatial` | 100 | 0 | 46 | 0 | 54 | 0 | 0.00% |
| Spatial | `select_poker_spatial` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| Spatial | `select_toy_spatial` | 100 | 84 | 11 | 0 | 0 | 5 | 84.00% |

## 6. 안정 실행 가능 task

| 카테고리 | Task | 전체 | XB0 | XB1 | XB2 | XB3 | XB4 | XB0 비율 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M&T | `select_billiards` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| M&T | `select_poker` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| Semantic | `select_poker_semantic` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| Spatial | `select_poker_spatial` | 100 | 100 | 0 | 0 | 0 | 0 | 100.00% |
| CommenSence | `select_nth_largest_poker` | 100 | 99 | 1 | 0 | 0 | 0 | 99.00% |
| CommenSence | `select_billiards_common_sense` | 100 | 97 | 0 | 1 | 2 | 0 | 97.00% |
| CommenSence | `select_fruit_common_sense` | 100 | 97 | 1 | 0 | 0 | 2 | 97.00% |
| M&T | `select_fruit` | 100 | 97 | 1 | 0 | 0 | 2 | 97.00% |
| Semantic | `select_fruit_semantic` | 100 | 97 | 1 | 0 | 0 | 2 | 97.00% |
| M&T | `select_chemistry_tube` | 100 | 94 | 4 | 0 | 0 | 2 | 94.00% |
| Semantic | `select_chemistry_tube_semantic` | 100 | 94 | 4 | 0 | 1 | 1 | 94.00% |
| Spatial | `select_chemistry_tube_spatial` | 100 | 92 | 4 | 0 | 0 | 4 | 92.00% |

## 7. Main denominator 제외 task

| 카테고리 | Task | XB0 | 주요 실패 양상 |
| --- | --- | --- | --- |
| CommenSence | `add_condiment_common_sense` | 0 / 100 | 조건 실패 94개, 비결정성 6개 |
| PhysicsLaw | `reflection_qa` | 0 / 100 | native 예외 100개 |
| Semantic | `add_condiment_semantic` | 0 / 100 | 조건 실패 98개, 비결정성 2개 |
| Semantic | `select_billiards_semantic` | 0 / 100 | native 예외 100개 |
| Spatial | `add_condiment_spatial` | 0 / 100 | 조건 실패 99개, 비결정성 1개 |
| Spatial | `select_fruit_spatial` | 0 / 100 | 조건 실패 46개, timeout 54개 |

## 8. Timeout 집중 분석

| 카테고리 | Task | XB3 timeout | 전체 대비 |
| --- | --- | --- | --- |
| Spatial | `select_fruit_spatial` | 54 / 100 | 54.00% |
| CommenSence | `select_billiards_common_sense` | 2 / 100 | 2.00% |
| Semantic | `select_chemistry_tube_semantic` | 1 / 100 | 1.00% |

## 9. Native exception 집중 분석

| 카테고리 | Task | XB2 native 예외 | 전체 대비 |
| --- | --- | --- | --- |
| PhysicsLaw | `reflection_qa` | 100 / 100 | 100.00% |
| Semantic | `select_billiards_semantic` | 100 / 100 | 100.00% |
| CommenSence | `select_chemistry_tube_common_sense` | 8 / 100 | 8.00% |
| CommenSence | `insert_flower_common_sense` | 4 / 100 | 4.00% |
| CommenSence | `select_billiards_common_sense` | 1 / 100 | 1.00% |
| M&T | `insert_flower` | 1 / 100 | 1.00% |

## 10. 반복 실행 비결정성 분석

| 카테고리 | Task | XB4 비결정성 | 전체 대비 |
| --- | --- | --- | --- |
| PhysicsLaw | `magnetism_qa` | 37 / 100 | 37.00% |
| PhysicsLaw | `speed_of_sound_qa` | 33 / 100 | 33.00% |
| PhysicsLaw | `thermal_expansion_qa` | 33 / 100 | 33.00% |
| PhysicsLaw | `density_qa` | 30 / 100 | 30.00% |
| PhysicsLaw | `friction_qa` | 29 / 100 | 29.00% |
| CommenSence | `select_drink_common_sense` | 22 / 100 | 22.00% |
| M&T | `select_book` | 22 / 100 | 22.00% |
| Semantic | `insert_flower_semantic` | 21 / 100 | 21.00% |

## 11. Evidence 완전성

최신 evidence audit 기준으로 rows with missing evidence는 0개이며, missing file counts는 `{}`이다. 즉, Track B taxonomy에 사용된 4,000개 sample은 모두 case-level evidence를 가진다.

## 12. Figure 목록

- `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\figures\track_b_taxonomy_distribution.png`
- `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\figures\track_b_taxonomy_by_category.png`
- `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\figures\track_b_task_eligible_rate.png`
- `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\figures\track_b_timeout_concentration.png`
- `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\figures\track_b_taxonomy_flow.png`

## 13. 논문 작성용 문장

본 연구는 VLABench public VLM evaluation subset 중 S0 generic-compatible 4,000개 sample에 대해 VLABench official expert를 2회 반복 실행하여 execution eligibility를 검증하였다. 그 결과 2133개 sample만이 두 반복 모두에서 성공했으며, 나머지 1867개는 조건 실패, native 예외, timeout, 반복 실행 비결정성으로 분류되었다. 따라서 이후 Qwen-guided execution 및 SILVER replanning 평가는 official expert가 재현 가능하게 성공한 2133개 sample을 main denominator로 사용하고, 나머지 sample은 diagnostic set으로 유지한다.

이 절차는 쉬운 sample을 임의로 고르는 cherry-picking이 아니라, VLM planning 실패와 native execution 계층 실패를 분리하기 위한 선행 검증이다.

## 14. Evidence files

- Source summary: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\metrics\s0_full_4000_preload_target_official_summary.json`
- Source results: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\metrics\s0_full_4000_preload_target_official_results.csv`
- Source task summary: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\metrics\s0_full_4000_preload_target_summary_by_task.csv`
- Taxonomy summary CSV: `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\metrics\track_b_taxonomy_summary.csv`
- Taxonomy by category CSV: `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\metrics\track_b_taxonomy_by_category.csv`
- Taxonomy by task CSV: `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\metrics\track_b_taxonomy_by_task.csv`
- Excluded diagnostic ledger JSONL: `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\metrics\track_b_excluded_diagnostic_ledger.jsonl`
- Taxonomy summary JSON: `silver\results\silver-official-guided-evaluation-20260516\track_b\taxonomy\metrics\track_b_taxonomy_summary.json`
- Evidence audit summary: `silver\results\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\evidence_audit\track_b_evidence_audit_summary.json`
