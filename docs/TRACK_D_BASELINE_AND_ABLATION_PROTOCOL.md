# Track D Baseline and Ablation Protocol

작성일: 2026-05-27  
문서 목적: Track D를 시작하기 전에 baseline, ablation, main comparison, 통계 분석, 논문 해석 범위를 고정한다.

## 1. 연구의 현재 위치

본 연구는 VLM의 로봇 조작 계획을 planning-only 정확도로만 평가하지 않고, official expert로 검증된 실행 가능 subset에서 실제 simulator execution까지 연결해 평가한다. Track A, B, C는 다음 역할을 갖는다.

| Track | 역할 | 현재 상태 |
|---|---|---|
| Track A | Qwen planning-only 평가 | VLABench planning artifact 확보 |
| Track B | official expert 기반 실행 가능 denominator 선별 | official eligible subset 확보 |
| Track C | Qwen-guided execution 평가 | 2,133개 완료, C0-C4 taxonomy 정리 |
| Track D | 실패 후 재계획 회복률 평가 | 본 문서 기준으로 착수 |

Track C 최종 결과는 다음과 같다.

| 상태 | 의미 | 개수 | 비율 |
|---|---|---:|---:|
| C0 | Qwen-guided execution success | 1,093 | 51.24% |
| C1 | 실행은 됐지만 condition failure | 790 | 37.04% |
| C2 | Qwen plan conversion failure | 210 | 9.85% |
| C3 | entity mapping failure | 39 | 1.83% |
| C4 | unsupported skill | 1 | 0.05% |

Track D의 출발점은 Track C의 실패 case다. 실패 후보는 C1-C4 총 1,040개다.

## 2. 핵심 연구 질문

Track D의 핵심 질문은 다음 하나로 고정한다.

> 실패한 Qwen initial plan에 대해, failure-aware SILVER replan은 동일 plan 재실행보다 실제 recovery를 더 많이 만드는가?

이를 정량화하는 main metric은 다음이다.

```text
Attributed Recovery Gain
= SILVER Replan Success Rate - Same-plan Retry Success Rate
```

이 지표가 필요한 이유는 simulator execution에는 비결정성, 물리 시뮬레이션 흔들림, 경로 계획 변동이 존재할 수 있기 때문이다. 단순히 replan 성공률만 보고 성능 개선을 주장하면 “그냥 다시 실행해서 성공한 것 아닌가?”라는 반박을 막기 어렵다. 따라서 same-plan retry를 반드시 paired baseline으로 둔다.

## 3. Baseline과 비교 조건

논문에서 사용할 비교 조건은 다음 네 가지다.

| 조건 | 역할 | 사용 위치 | 논문 해석 |
|---|---|---|---|
| Official Expert | 실행 가능 sample 선별 기준 | Track B | competing planner가 아니라 eligibility oracle |
| Initial Qwen | 재계획 전 기본 성능 | Track C | VLM initial planning의 execution success |
| Same-plan Retry | 단순 재시도 baseline | Track D | simulator 비결정성 및 retry 효과 통제 |
| SILVER Replan | 제안 방법 | Track D | failure evidence 기반 plan revision 효과 |

중요한 원칙:

- Official Expert는 VLM과 경쟁하는 planner baseline이 아니다.
- Official Expert는 “이 sample이 실행 평가 denominator로 사용 가능한가”를 판단하는 기준이다.
- Initial Qwen은 Track D의 failure source이자 Track C의 main baseline이다.
- Same-plan Retry는 SILVER의 recovery claim을 방어하기 위한 필수 baseline이다.
- SILVER Replan은 same-plan retry 대비 recovery gain으로 평가한다.

## 4. Main Comparison

Track D의 main comparison은 다음 두 조건의 paired comparison이다.

| 조건 | 입력 plan | failure evidence 사용 | 목적 |
|---|---|---|---|
| Same-plan Retry | Track C initial Qwen plan 그대로 사용 | 사용하지 않음 | 단순 재실행으로 회복되는 비율 측정 |
| SILVER Replan | Qwen이 새 plan 생성 | 사용함 | 실패 증거 기반 plan revision 효과 측정 |

모든 case는 동일 sample, 동일 instruction, 동일 initial Qwen plan에서 출발한다. Same-plan Retry와 SILVER Replan은 같은 failure case에 대해 paired design으로 실행한다.

## 5. SILVER Replan 입력 고정 원칙

SILVER Replan은 실패 유형별로 별도 prompt를 만들지 않는다. 모든 case에 대해 같은 prompt template과 같은 JSON schema를 사용한다. 단, template 내부의 evidence field 값은 case의 실제 artifact에 따라 채워진다.

### 5.1 공통 입력 필드

SILVER Replan prompt에는 다음 항목만 제공한다.

| 필드 | 설명 | 허용 여부 |
|---|---|---|
| `instruction` | 원래 task instruction | 허용 |
| `initial_plan` | Track C에서 사용한 Qwen initial plan | 허용 |
| `failure_observation.execution_status` | 실행/변환 상태 | 허용 |
| `failure_observation.condition_success` | task condition 성공 여부 | 허용 |
| `failure_observation.progress_score` | VLABench progress score | 허용 |
| `failure_observation.symptom_log` | 실패 증상 요약 | 허용 |
| `failure_observation.stage_trace_summary` | 실행 stage 요약 | R4 ablation에서만 허용 |
| `failure_observation.final_visual_evidence` | final/failure mosaic | R2/R3/R4에서 허용 |
| `allowed_skill_schema` | 허용 skill과 parameter schema | 허용 |
| `output_json_schema` | 출력 JSON schema | 허용 |

### 5.2 금지 입력

다음 정보는 어떤 조건에서도 제공하지 않는다.

- GT operation sequence
- GT object 이름
- GT target 이름
- Official expert action sequence
- 정답 entity id
- “이 물체를 고르면 된다”와 같은 직접 정답 힌트
- 사람이 수동으로 고친 plan

이 금지 원칙은 Track D의 학술적 방어력에 중요하다. Replan 성능이 정답 유출 때문이 아니라 failure evidence와 schema guidance 때문임을 보장해야 한다.

## 6. Replanning Feedback Ablation

Track D의 main condition은 R3로 고정한다.

```text
R3 = failure image + symptom log
```

R3를 main condition으로 두는 이유는 다음과 같다.

- C1 case는 실제 execution artifact가 있으므로 final image와 symptom log를 모두 제공할 수 있다.
- failure text만으로는 시각적 target/object 오류를 충분히 설명하기 어렵다.
- image만으로는 어떤 stage가 실패했는지 알기 어렵다.
- executed trace까지 모두 주는 R4는 정보량이 많아 upper-bound 성격이 강하다.

### 6.1 Ablation 조건 정의

| 조건 | 제공 정보 | 목적 | main/ablation |
|---|---|---|---|
| R0 | replan 없음 | Initial Qwen failure baseline | baseline |
| SR | same-plan retry | 단순 재실행 효과 측정 | baseline |
| NF | no-feedback replan | 실패 정보 없이 다시 계획했을 때 효과 | ablation |
| R1 | symptom log only | 텍스트 실패 정보 효과 | ablation |
| R2 | final/failure image only | 시각 실패 정보 효과 | ablation |
| R3 | final/failure image + symptom log | SILVER main condition | main |
| R4 | final/failure image + symptom log + executed trace | trace 추가 효과 및 upper-bound | optional ablation |

### 6.2 조건별 비교 질문

| 비교 | 질문 |
|---|---|
| R3 vs SR | failure-aware replan이 단순 재실행보다 좋은가? |
| R3 vs NF | 실패 정보가 없는 재출력보다 failure evidence가 도움이 되는가? |
| R1 vs R2 | 텍스트 실패 정보와 시각 실패 정보 중 무엇이 더 도움이 되는가? |
| R4 vs R3 | stage trace를 추가하면 recovery가 더 좋아지는가? |

논문 main table에는 SR, NF, R3를 우선 배치한다. R1/R2/R4는 ablation table로 분리한다.

## 7. Track D 대상 구성

Track D 전체 후보는 Track C 실패 case C1-C4다.

| 상태 | 개수 | Track D 처리 |
|---|---:|---|
| C1 | 790 | main recovery 대상 |
| C2 | 210 | conversion failure recovery 대상 |
| C3 | 39 | entity grounding recovery 대상 |
| C4 | 1 | unsupported skill diagnostic |

### 7.1 Primary Set

Primary set은 C1 전체 790개로 둔다.

이유:

- C1은 실제 execution artifact가 존재한다.
- final image, stage log, progress score를 제공할 수 있다.
- 실패 후 재계획이라는 SILVER의 핵심 설정과 가장 잘 맞는다.
- same-plan retry와 replan을 공정하게 비교할 수 있다.

### 7.2 Secondary Diagnostic Set

C2, C3, C4는 secondary diagnostic set으로 둔다.

| 상태 | 이유 |
|---|---|
| C2 | 실행 전 conversion failure라 final execution image가 없거나 제한적이다. replan 가능성은 있지만 C1과 동일하게 해석하면 안 된다. |
| C3 | entity mapping 실패이므로 recovery가 object naming/grounding correction에 집중된다. |
| C4 | 표본 수가 1개뿐이라 정량 분석보다 사례 분석에 적합하다. |

Main claim은 C1 primary set을 중심으로 작성하고, C2-C4는 failure-type subgroup analysis로 제시한다.

## 8. Planning Input Ablation과의 관계

Track A의 P1/P2/P3는 planning input ablation이다.

| 조건 | 입력 | 목적 |
|---|---|---|
| P1 | raw input image + instruction + schema | 기본 visual planning |
| P2 | input mask + instruction + schema | visual grounding 보조 효과 |
| P3 | image + instruction + explicit skill/parameter schema | schema guidance 효과 |

Track C와 D의 main pipeline은 P2를 기준으로 한다.

이유:

- P2는 Track A에서 이미 생성된 주요 condition이다.
- mask image는 object grounding을 돕지만 GT action을 직접 제공하지 않는다.
- Track C 결과가 P2 기반으로 확보되어 있으므로 Track D도 P2 실패 case에서 이어지는 것이 가장 일관적이다.

P1/P3 기반 execution까지 확장하는 것은 optional이다. 현재 논문 main story에서는 P1/P2/P3를 planning-only ablation으로 사용하고, execution/replanning은 P2 기준으로 고정한다.

## 9. 출력 및 평가 지표

### 9.1 Case-level 기록

각 Track D case는 다음 artifact를 가져야 한다.

```text
track_d/
  data/<category>/<task>/<example>/
    initial_qwen_plan.json
    initial_failure_summary.json
    same_plan_retry/
      execution_result.json
      initial_mosaic.png
      final_mosaic.png
      orchestrator.log
    replan_R3/
      prompt.json
      raw_output.json
      parsed_output.json
      adapter_validation.json
      executor_plan.json
      execution_result.json
      initial_mosaic.png
      final_mosaic.png
      orchestrator.log
```

R1/R2/R4 ablation을 실행하는 경우에는 `replan_R1`, `replan_R2`, `replan_R4` 폴더를 별도로 둔다.

### 9.2 Main metrics

| 지표 | 정의 |
|---|---|
| Same-plan Retry Success Rate | Same-plan Retry 성공 case / 대상 case |
| SILVER Replan Success Rate | R3 Replan 성공 case / 대상 case |
| Attributed Recovery Gain | SILVER Replan Success Rate - Same-plan Retry Success Rate |
| Replan Conversion Failure Rate | replan 출력이 실행 가능한 plan으로 변환되지 않은 비율 |
| Replan Unsupported Skill Rate | replan이 허용되지 않은 skill을 제안한 비율 |
| Recovery by Failure Type | C1/C2/C3/C4별 recovery rate |

### 9.3 Attribution taxonomy

성공/실패 결과는 다음 taxonomy로 정리한다.

| Label | 의미 |
|---|---|
| A0 | 회복 없음 |
| A1 | same-plan retry로 회복 |
| A2 | format/schema 수정으로 회복 |
| A3 | object/target 수정으로 회복 |
| A4 | action sequence 수정으로 회복 |
| A5 | recovery strategy 수정으로 회복 |
| A6 | unsupported action 제안 |
| A7 | 실행 계층 confound |

A7은 main recovery gain 계산에서 별도 보고한다. A7이 발생하면 모델 실패로 합산하지 않고 diagnostic으로 분리한다.

## 10. 통계 분석 계획

Track D는 paired design이다. 같은 실패 case에 대해 same-plan retry와 SILVER replan을 비교한다.

### 10.1 Main statistical test

| 비교 | 검정 |
|---|---|
| SR 성공/실패 vs R3 성공/실패 | McNemar test |
| R1/R2/R3/R4 다조건 성공률 | Cochran's Q |
| recovery gain confidence interval | bootstrap 95% CI |
| latency 비교 | Wilcoxon signed-rank test |

### 10.2 Multiple comparison correction

R1/R2/R3/R4/NF 등 여러 조건을 비교할 경우 Holm-Bonferroni correction을 적용한다.

### 10.3 Effect size

성공률 차이는 percentage point로 보고하고, paired binary comparison은 odds ratio 또는 risk difference를 함께 제시한다.

## 11. 논문 주장 가능 범위

Track D 결과가 좋을 때 주장 가능한 내용:

- failure-aware replanning은 same-plan retry보다 높은 recovery를 보인다.
- recovery는 모든 실패에서 동일하게 발생하지 않고, failure type에 따라 차이가 있다.
- C1 condition failure는 C2 conversion failure보다 recovery 가능성이 높을 수 있다.
- final image와 symptom log의 조합은 단일 modality failure evidence보다 효과적일 수 있다.

Track D 결과가 제한적일 때도 주장 가능한 내용:

- planning-only 성능과 execution success 사이의 gap은 여전히 유효하다.
- 실패 taxonomy는 replan 가능/불가능 실패를 구분하는 데 필요하다.
- same-plan retry baseline이 없으면 recovery claim이 과대평가될 수 있다.
- VLM의 visual grounding 한계가 replan 단계에서도 반복될 수 있다.

주장하면 안 되는 내용:

- SILVER가 로봇 제어 성능을 개선했다.
- Qwen이 일반적인 로봇 조작을 안정적으로 수행한다.
- VLABench 전체 task에 대해 sim-to-real 성능을 보장한다.
- Official expert보다 Qwen이 우수하다는 식의 비교.

## 12. 논문용 핵심 표 구성

### Table 1. Experimental Tracks

Track A/B/C/D의 역할, 대상 수, 산출물을 요약한다.

### Table 2. Baseline and Proposed Conditions

Official Expert, Initial Qwen, Same-plan Retry, SILVER Replan의 역할을 구분한다.

### Table 3. Track C Failure Taxonomy

C0-C4 결과를 제시한다.

### Table 4. Track D Main Recovery Result

| Condition | 대상 | 성공 | 성공률 | Initial failure 대비 회복 | SR 대비 gain |
|---|---:|---:|---:|---:|---:|
| Same-plan Retry | TBD | TBD | TBD | TBD | - |
| SILVER Replan R3 | TBD | TBD | TBD | TBD | TBD |

### Table 5. Replanning Ablation

NF, R1, R2, R3, R4 조건별 recovery를 제시한다.

### Table 6. Recovery by Failure Type

C1/C2/C3/C4별 recovery rate를 제시한다.

## 13. 실행 순서

Track D는 다음 순서로 진행한다.

1. Track C 실패 case C1-C4 manifest 생성
2. C1 primary set과 C2-C4 diagnostic set 분리
3. Same-plan Retry 실행
4. R3 SILVER Replan prompt 생성
5. Qwen replan inference 실행
6. replan output validation 및 adapter conversion
7. replan execution 실행
8. SR vs R3 paired metric 계산
9. NF/R1/R2/R4 ablation 실행
10. attribution taxonomy 생성
11. 통계 분석 및 최종 보고서 작성

## 14. 최종 정리

현재 연구의 학술적 구조는 다음과 같이 정리된다.

```text
Track A: VLM planning-only 성능 측정
Track B: official expert로 실행 가능 denominator 통제
Track C: Qwen-guided execution에서 plan-to-execution gap 측정
Track D: failure-aware replanning이 same-plan retry보다 recovery에 기여하는지 검증
```

Baseline은 Initial Qwen과 Same-plan Retry를 중심으로 하고, Official Expert는 eligibility oracle로 사용한다. Ablation은 planning input ablation(P1/P2/P3)과 replanning feedback ablation(NF/R1/R2/R3/R4)으로 분리한다. Main claim은 R3 SILVER Replan이 same-plan retry 대비 얼마나 recovery gain을 만드는지에 한정한다.
