# SILVER 전체 실험 결과 보고서: 피드백 반영 재분석본

작성일: 2026-06-02  
분석 범위: 기존 저장 artifact 기반 재분석. 추가 실험 없음.  
핵심 제안 방법: `R3`, failure/final image + symptom log 기반 SILVER replanning

## 1. 요약 판단

현재 결과는 논문으로 전개 가능한 구조를 가진다. 특히 Track B에서 official expert 실행 가능성을 먼저 검증하고, Track C에서 initial Qwen-guided execution 실패 집합을 정의한 뒤, Track D에서 동일한 1,040개 실패 case에 대해 `SR`과 `R3`를 paired comparison으로 비교한 구조는 학술적으로 방어 가능하다.

다만 해석은 조건부로 제한해야 한다. 본 연구는 “VLABench 전체에서 SILVER가 일반적으로 우수하다”는 주장이 아니라, **VLABench official-expert-eligible subset에서 Qwen-guided execution 실패 case를 대상으로 failure-aware replanning이 same-plan retry보다 유의하게 높은 회복률을 보였다**는 주장으로 정리해야 한다.

## 2. 전체 실험 구조

| Track | 목적 | 평가 단위 | 핵심 산출물 |
| --- | --- | ---: | --- |
| Track A | Public VLM planning 평가 | 4,500 samples x P1/P2/P3 = 13,500 outputs | Qwen planning 정확도, P2 main output 선정 |
| Track B | Official expert execution eligibility 검증 | S0 generic-compatible 4,000 samples | official eligible 2,133개 확정 |
| Track C | Initial Qwen-guided official execution | Track B eligible 2,133 samples | Initial Qwen 성공 1,093개, 실패 1,040개 |
| Track D | Conditional recovery 평가 | Track C 실패 1,040 samples | `SR` vs `R3` paired comparison |
| Track D Ablation | feedback 구성요소 분석 | Track D 1,040개 중 stratified 300 samples | `NF/R1/R2/R3/R4` 비교 |

논문 본문에서는 아래 sample flow를 별도 figure로 제시하는 것이 필요하다. 이 흐름을 명시해야 Track B filtering이 cherry-picking이 아니라 execution eligibility 분리 과정임을 방어할 수 있다.

```text
VLABench public VLM samples: 4,500
        |
        v
S0 generic-compatible samples: 4,000
        |
        v  Track B official expert eligibility
Official-expert-eligible: 2,133
Official-ineligible: 1,867
        |
        v  Track C initial Qwen-guided execution
Initial success: 1,093
Initial failure: 1,040
        |
        v  Track D conditional recovery
SR recovered: 36
R3 recovered: 326
```

## 3. Track A: Public VLM Planning Evaluation

### 3.1 목적

Track A는 VLABench public VLM evaluation sample에서 Qwen이 high-level operation sequence를 얼마나 잘 생성하는지 평가한 non-interactive planning benchmark다.

### 3.2 결과

| 조건 | n | Schema valid | Exact match | Skill accuracy | Action recall | Order accuracy | Step F1 | Edit distance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `P1` | 4,500 | 73.4% | 0.0% | 48.0% | 48.9% | 25.0% | 0.0% | 2.399 |
| `P2` | 4,500 | 79.8% | 13.2% | 50.1% | 50.9% | 25.6% | 31.4% | 1.731 |
| `P3` | 4,500 | 80.2% | 0.0% | 45.4% | 56.1% | 27.1% | 0.0% | 2.830 |

`P2`는 exact match와 step-level F1 기준으로 가장 유효한 condition으로 나타났다. 따라서 Track C/D의 initial Qwen plan에는 P2 output을 사용했다.

### 3.3 보수적 해석

Track A에서 `P1`과 `P3`의 exact match 및 step F1이 0.0%로 나타난 것은 metric/evaluator normalization 이슈 가능성을 배제할 수 없다. 특히 `P3`는 schema valid와 action recall은 높지만 step F1이 0.0%이므로, 논문 본문에서는 Track A를 “P2를 main planning output으로 선택한 근거” 정도로 제한해 사용하는 것이 안전하다. 제출 전에는 P1/P3 raw output 일부와 evaluator normalization을 별도 audit하는 것이 바람직하다.

## 4. Track B: Official Expert Eligibility

### 4.1 목적

Track B는 Qwen 성능 평가가 아니라, VLABench sample을 native execution denominator로 사용할 수 있는지 검증하는 단계다. official expert가 2회 모두 성공한 sample만 Track C/D main denominator로 사용했다.

### 4.2 결과

| 상태 | 개수 | 비율 | 해석 |
| --- | ---: | ---: | --- |
| `B0_official_eligible` | 2,133 | 53.3% | Track C/D main denominator |
| `B1_condition_failure` | 1,217 | 30.4% | official execution 완료 후 success condition 실패 |
| `B3_native_exception` | 214 | 5.4% | native exception/crash |
| `B4_timeout` | 57 | 1.4% | 300초 timeout |
| `B5_nondeterministic_mismatch` | 379 | 9.5% | 2회 반복 결과 불일치 |
| 합계 | 4,000 | 100.0% |  |

### 4.3 카테고리별 결과

| Category | 전체 | Eligible | Eligible rate |
| --- | ---: | ---: | ---: |
| CommenSence | 800 | 519 | 64.9% |
| M&T | 900 | 616 | 68.4% |
| PhysicsLaw | 600 | 42 | 7.0% |
| Semantic | 900 | 507 | 56.3% |
| Spatial | 800 | 449 | 56.1% |

### 4.4 보수적 해석

Track B의 2,133개 denominator는 cherry-picking이 아니라 native execution confound를 분리하기 위한 eligibility filtering이다. 다만 PhysicsLaw의 eligible rate가 7.0%로 매우 낮기 때문에, 논문에서는 “VLABench 전체”가 아니라 **official-expert-eligible subset**에서의 결과라고 명확히 표현해야 한다.

권장 표현:

> On the official-expert-eligible subset of VLABench public VLM evaluation samples, SILVER improves recovery from Qwen-guided execution failures.

피해야 할 표현:

> SILVER improves replanning on all VLABench tasks.

## 5. Track C: Initial Qwen-Guided Execution

### 5.1 목적

Track C는 Track B에서 official eligible로 검증된 2,133개 sample에 대해 Qwen P2 output을 official-guided execution으로 연결했을 때 실제 task success가 발생하는지 평가했다.

### 5.2 결과

| 상태 | 개수 | 비율 | 의미 |
| --- | ---: | ---: | --- |
| `C0_qwen_guided_success` | 1,093 | 51.2% | Initial Qwen 실행 성공 |
| `C1_qwen_guided_condition_failure` | 790 | 37.0% | 실행 완료, 조건 실패 |
| `C2_qwen_conversion_failure` | 210 | 9.8% | Qwen output 변환 실패 |
| `C3_entity_mapping_failure` | 39 | 1.8% | object/target grounding 실패 |
| `C4_unsupported_qwen_skill` | 1 | 0.05% | unsupported skill |
| 합계 | 2,133 | 100.0% |  |

Initial Qwen은 2,133개 중 1,093개를 성공시켰고, 나머지 1,040개가 Track D의 conditional recovery 대상이 됐다.

## 6. Track D: Conditional Recovery Full Evaluation

### 6.1 목적

Track D는 Track C에서 실패한 1,040개 case를 대상으로, 실패 plan을 그대로 다시 실행하는 `SR`과 failure-aware feedback을 제공하는 `R3(SILVER)`를 paired design으로 비교했다.

### 6.2 Main conditional recovery 결과

| Method | 입력 | Denominator | Success | Recovery rate | 95% CI |
| --- | --- | ---: | ---: | ---: | ---: |
| `SR` | same failed plan | 1,040 | 36 | 3.5% | 2.5-4.8% |
| `R3` SILVER | failure/final image + symptom log | 1,040 | 326 | 31.3% | 28.6-34.2% |

`R3 - SR`의 paired recovery gain은 +27.9%p이며, bootstrap 95% CI는 25.0-30.8%p다.

### 6.3 Pairwise contingency table

|  | R3 success | R3 fail | Total |
| --- | ---: | ---: | ---: |
| SR success | 24 | 12 | 36 |
| SR fail | 302 | 702 | 1,004 |
| Total | 326 | 714 | 1,040 |

McNemar exact test 결과는 `p = 9.67e-74`로, R3와 SR의 차이는 매우 강하다. 이 표는 단순 marginal success rate가 아니라 동일한 1,040개 case에 대한 paired comparison이므로 main claim의 핵심 근거로 사용해야 한다.

### 6.4 Attribution 결과

Attribution은 `SR`과 `R3`의 paired outcome을 4분할로 해석해야 한다. `SR` 성공 36건 중 24건은 `R3`도 성공했기 때문에, 36건 전체를 “단순 재시도만으로 회복”이라고 표현하면 부정확하다.

| Attribution class | Count | 의미 |
| --- | ---: | --- |
| Both SR and R3 recovered | 24 | 단순 재시도와 R3가 모두 성공 |
| SR-only recovered | 12 | SR만 성공하고 R3는 실패 |
| R3-only recovered | 302 | R3만 성공하고 SR은 실패 |
| Neither recovered | 702 | 둘 다 실패 |
| Total | 1,040 |  |

따라서 paired recovery gain은 단순히 `326 - 36`의 marginal 차이로만 설명하기보다, discordant pair를 사용해 다음처럼 표현하는 것이 가장 정확하다.

```text
Paired recovery gain = (R3-only - SR-only) / 1,040
                     = (302 - 12) / 1,040
                     = 27.9%p
```

### 6.5 End-to-end 관점 재계산

Track D는 conditional recovery 실험이므로 Initial Qwen을 1,040개 failure set에서 0% baseline으로만 제시하면 denominator conditioning 문제가 생길 수 있다. 따라서 end-to-end success도 함께 제시해야 한다.

| System | Total success | Total rate | 해석 |
| --- | ---: | ---: | --- |
| Initial Qwen only | 1,093 / 2,133 | 51.2% | 최초 실행 성공률 |
| Initial Qwen + SR | 1,129 / 2,133 | 52.9% | 단순 재시도 추가 |
| Initial Qwen + R3 | 1,419 / 2,133 | 66.5% | SILVER 재계획 추가 |

End-to-end 기준으로도 R3는 initial-only 대비 +15.3%p를 제공한다.

## 7. Track D Ablation: Feedback 구성요소 분석

### 7.1 목적과 subset

Ablation은 Track D 전체 1,040개 failure set 중 stratified 300개 subset에서 수행했다. 이 결과는 full-scale main result가 아니라 feedback 구성요소 분석이다.

초기 실패 유형 분포:

| Initial failure type | 개수 |
| --- | ---: |
| `C1_condition_failure` | 220 |
| `C2_conversion_failure` | 60 |
| `C3_entity_mapping_failure` | 19 |
| `C4_unsupported_skill` | 1 |
| 합계 | 300 |

### 7.2 Ablation marginal results

| Method | Feedback information | Success | Success rate | 95% CI |
| --- | --- | ---: | ---: | ---: |
| `SR` | same plan | 14 / 300 | 4.7% | 2.8-7.7% |
| `NF` | no failure feedback | 51 / 300 | 17.0% | 13.2-21.7% |
| `R1` | symptom log only | 75 / 300 | 25.0% | 20.4-30.2% |
| `R2` | failure/final image only | 41 / 300 | 13.7% | 10.2-18.0% |
| `R3` SILVER | image + symptom log | 85 / 300 | 28.3% | 23.5-33.7% |
| `R4` | image + symptom log + executed trace | 78 / 300 | 26.0% | 21.4-31.2% |

### 7.3 Ablation pairwise comparison against R3

| 비교 | R3-only | 비교 조건 only | Net gain | McNemar p | Bootstrap 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| R3 vs SR | 77 | 6 | +23.7%p | 8.45e-17 | 18.3-29.0%p |
| R3 vs NF | 63 | 29 | +11.3%p | 5.09e-4 | 5.3-17.7%p |
| R3 vs R1 | 47 | 37 | +3.3%p | 0.326 | -2.7-9.3%p |
| R3 vs R2 | 48 | 4 | +14.7%p | 1.31e-10 | 10.3-19.0%p |
| R3 vs R4 | 21 | 14 | +2.3%p | 0.311 | -1.3-6.0%p |

### 7.4 보수적 ablation 해석

R3는 ablation subset에서 가장 높은 point estimate를 보였다. SR, NF, R2 대비 차이는 명확하다. 반면 R1 및 R4와의 차이는 작고 paired test에서도 유의하다고 보기 어렵다. 따라서 논문에서는 “R3가 모든 feedback 조건보다 통계적으로 우월하다”고 주장하지 않는 것이 안전하다.

권장 해석:

> R3 achieved the highest point estimate among feedback configurations. The gain over SR, NF, and image-only R2 was substantial, while the marginal gains over log-only R1 and trace-augmented R4 were modest.

한국어 해석:

> R3는 feedback ablation에서 가장 높은 점추정치를 보였고, SR/NF/R2 대비 개선은 명확했다. 다만 R1 및 R4 대비 차이는 작으므로, symptom log가 핵심 정보이고 image는 이를 보완하는 맥락 정보를 제공하는 것으로 해석하는 것이 안전하다.

### 7.5 R2/R4 해석 주의

`R2`가 `NF`보다 낮다는 결과는 “이미지가 무용하다”는 뜻이 아니다. 현재 prompt/execution setting에서는 failure/final image만으로는 failure diagnosis와 corrective planning을 안정적으로 유도하기 어렵다는 뜻으로 제한해야 한다.

`R4`가 `R3`보다 낮다는 결과도 “trace가 항상 나쁘다”는 뜻이 아니다. executed trace가 verbose/noisy context로 작용했을 가능성이 있으며, structured trace 또는 summarized trace는 별도 연구가 필요하다.

## 8. Failure taxonomy 명명 정리

보고서와 논문에서는 두 종류의 taxonomy를 분리해야 한다.

| 명칭 | 의미 | 예 |
| --- | --- | --- |
| Initial failure type distribution | ablation subset을 뽑을 때의 원래 Track C 실패 유형 | C1 220, C2 60, C3 19, C4 1 |
| Post-replanning outcome taxonomy | 각 method 실행 후의 결과 상태 | R3에서 C0 85, C1 76, C2 54, C3 85 |

두 표를 같은 “failure taxonomy”로 부르면 혼동이 생긴다. 논문에서는 “initial failure strata”와 “post-replanning outcome”으로 명확히 분리하는 것이 좋다.

## 9. 현재 데이터만으로 반영 완료한 수정사항

추가 실험 없이 기존 artifact만으로 다음 항목을 반영했다.

| 항목 | 반영 내용 |
| --- | --- |
| Denominator 분리 | Track C initial success와 Track D conditional recovery 분리 |
| End-to-end success | Initial only, Initial+SR, Initial+R3 재계산 |
| Main pairwise table | SR/R3 2x2 contingency table 추가 |
| Main statistical test | McNemar exact p-value 및 paired bootstrap CI 추가 |
| Ablation 보수 해석 | R3 vs R1/R4는 modest gain으로 표현 |
| Ablation pairwise test | R3 대비 각 조건의 McNemar p-value 및 bootstrap CI 추가 |
| R2/R4 해석 보정 | image-only/trace 조건의 과해석 방지 |
| Track B selection bias | official-expert-eligible subset으로 claim 제한 |
| Taxonomy 명명 | initial failure strata와 post-replanning outcome 분리 |
| Track A caveat | P1/P3 metric audit 필요성을 명시 |

## 10. 아직 추가 실험이 필요한 항목

이번 재분석에서는 추가 실험을 하지 않았다. 따라서 아래 항목은 “미반영”이 아니라 “추가 실험 필요 항목”으로 분리한다.

| 항목 | 필요성 | 현재 상태 |
| --- | --- | --- |
| Schema/rule validator baseline | C2/C3 recovery가 단순 parser/entity repair인지 분리 | 미실험 |
| Oracle/structured-state subset | perception bottleneck과 planning bottleneck 분리 | 미실험 |
| Track A P1/P3 metric audit | evaluator normalization 문제 가능성 확인 | 미완료 |
| R1/R4 full 1,040 확장 | R3 vs R1/R4 차이 검정력 확대 | 미실험 |
| failure-log leakage audit | symptom log가 정답을 암시하지 않는지 검증 | 미실험 |

## 11. 논문에서 방어 가능한 주장

현재 데이터로 방어 가능한 주장은 다음과 같다.

1. Track B에서 official expert eligibility를 검증하지 않으면 execution benchmark denominator가 불안정해진다.
2. Official-expert-eligible subset 2,133개에서 Initial Qwen-guided execution은 51.2% 성공률을 보였다.
3. Initial Qwen 실패 1,040개에서 same-plan retry는 3.5%만 회복했다.
4. 동일한 1,040개 실패 case에서 SILVER R3는 31.3%를 회복했다.
5. Paired comparison 기준 R3-only success 302개, SR-only success 12개로 R3의 conditional recovery 효과는 매우 강하다.
6. End-to-end 기준 Initial+R3는 66.5%로 Initial only 51.2% 대비 +15.3%p 높다.
7. Ablation subset에서 R3는 가장 높은 point estimate를 보였고, SR/NF/R2 대비 명확한 개선을 보였다.

## 12. 피해야 할 주장

다음 표현은 현재 데이터만으로는 과도하다.

1. “SILVER가 VLABench 전체에서 일반적으로 우수하다.”
2. “R3가 R1/R4보다 통계적으로 확실히 우월하다.”
3. “이미지 정보는 재계획에 쓸모없다.”
4. “executed trace는 항상 성능을 낮춘다.”
5. “실제 로봇 조작 성능을 입증했다.”
6. “Track D failure set에서 Initial Qwen 대비 R3가 31.3%p 개선됐다.”

마지막 항목은 특히 주의해야 한다. Track D failure set은 Initial Qwen 실패 case만 모은 것이므로, 전체 기준 개선은 Initial only 51.2%에서 Initial+R3 66.5%로 상승한 +15.3%p로 표현해야 한다.

## 13. Evidence 경로

### Track A

- `C:\SILVER\archive\silver_track_ab_20260523\track_a_vlabench_planning_20260510\metrics\vlabench_planning_metrics_summary.json`

### Track B

- `C:\SILVER\archive\silver_track_ab_20260523\silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\metrics\s0_full_4000_preload_target_official_summary.json`
- `C:\SILVER\archive\silver_track_ab_20260523\silver-official-guided-evaluation-20260516\track_b\taxonomy\TRACK_B_FAILURE_TAXONOMY_REPORT.md`

### Track C

- `C:\SILVER\archive\silver_track_c_qwen_guided_20260524\metrics\qwen_guided_execution_summary.json`

### Track D

- `C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\metrics\track_d_R3_summary_all.json`
- `C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\metrics\track_d_same_plan_retry_all_summary.json`
- `C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\metrics\track_d_same_plan_vs_replan_R3_all.csv`

### Track D Ablation

- `C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\ablation_300\metrics\ablation_300_summary.json`
- `C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\ablation_300\metrics\ablation_300_pairwise_comparison.csv`
