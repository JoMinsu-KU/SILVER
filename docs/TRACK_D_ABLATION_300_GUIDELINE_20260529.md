# Track D Ablation 300건 실험 가이드라인

작성일: 2026-05-29  
문서 목적: Track D의 주 결과인 `SR vs R3` 전체 1,040건 paired comparison을 보완하기 위해, 실패 피드백 구성요소별 ablation 실험을 300건 subset에서 수행하는 기준을 고정한다.

---

## 1. 현재 완료된 Track D 주 결과

Track D main comparison은 이미 전체 실패 set 1,040건에서 완료되었다.

| 조건 | 의미 | 성공 | 분모 | 성공률 |
|---|---:|---:|---:|---:|
| SR | Same-plan retry | 36 | 1,040 | 3.46% |
| R3 | SILVER replan, failure image + symptom log | 326 | 1,040 | 31.35% |
| Recovery Gain | R3 - SR | +290 | 1,040 | +27.88%p |

이 결과는 논문의 main result로 사용한다.  
Ablation은 main result를 대체하지 않고, `왜 R3 구성이 타당한가`를 설명하기 위한 보조 실험이다.

---

## 2. Ablation의 연구 질문

Track D ablation은 다음 질문에 답해야 한다.

1. 실패 정보 없이 다시 계획하게 해도 성능이 좋아지는가?
2. 텍스트 실패 증상만 주면 도움이 되는가?
3. 실패 후 시각 정보만 주면 도움이 되는가?
4. 텍스트와 시각 실패 정보를 함께 줄 때 가장 실용적인 성능 향상이 발생하는가?
5. 실행 trace까지 주면 R3보다 더 좋아지는가, 아니면 정보량 증가 대비 이득이 제한적인가?

따라서 ablation의 핵심은 단순히 조건을 많이 돌리는 것이 아니라, R3가 제안 시스템으로 선택된 이유를 정량적으로 방어하는 것이다.

---

## 3. Ablation 대상 데이터셋

Ablation은 Track D 전체 failure set 1,040건에서 층화 추출한 300건 subset으로 수행한다.

전체 1,040건의 초기 Track C 실패 분포는 다음과 같다.

| 초기 실패 유형 | 의미 | 전체 건수 |
|---|---|---:|
| C1 | 실행은 됐지만 task condition 실패 | 790 |
| C2 | 초기 Qwen output이 executor plan으로 변환 실패 | 210 |
| C3 | object/target entity mapping 실패 | 39 |
| C4 | unsupported skill 제안 | 1 |
| 합계 |  | 1,040 |

300건 subset은 이 분포를 최대한 보존하되, C3/C4가 너무 적어지는 것을 막기 위해 다음 구성을 사용한다.

| 초기 실패 유형 | Ablation subset 건수 | 선정 이유 |
|---|---:|---|
| C1 | 220 | 실제 실행 후 실패한 primary recovery 대상 |
| C2 | 60 | schema/sequence 변환 실패 분석 |
| C3 | 19 | entity grounding 실패 분석을 위한 최소 표본 확보 |
| C4 | 1 | 전체 데이터에 1건뿐이므로 반드시 포함 |
| 합계 | 300 |  |

선정 방식:

- Track D 전체 1,040건 manifest에서 sampling한다.
- 각 failure type 내부에서는 고정 seed로 무작위 추출한다.
- seed는 `20260529`로 고정한다.
- sample id, category, task, example, initial failure type을 별도 manifest로 저장한다.
- 임의로 쉬운 case를 고르거나, 성공 가능성이 높아 보이는 case를 수동 선택하지 않는다.

필수 산출물:

```text
C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\ablation_300\manifest\track_d_ablation_300_manifest.jsonl
C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\ablation_300\manifest\track_d_ablation_300_summary_by_status.csv
```

---

## 4. Ablation 조건 정의

Track D ablation은 다음 네 조건을 새로 실행한다. R3는 이미 실행된 전체 결과에서 subset에 해당하는 300건만 재사용한다.

| 조건 | 제공 정보 | 목적 | 실행 여부 |
|---|---|---|---|
| NF | instruction + initial plan만 제공, 실패 정보 없음 | 단순 재질문 효과 측정 | 신규 실행 |
| R1 | instruction + initial plan + symptom log | 텍스트 실패 정보 효과 측정 | 신규 실행 |
| R2 | instruction + initial plan + failure/final image | 시각 실패 정보 효과 측정 | 신규 실행 |
| R3 | instruction + initial plan + symptom log + failure/final image | SILVER main condition | 기존 결과 재사용 |
| R4 | instruction + initial plan + symptom log + failure/final image + executed trace | trace 추가 upper-bound | 신규 실행 |

주의:

- R3는 ablation table에도 포함하지만 재실행하지 않는다.
- 동일 300건에 해당하는 기존 R3 inference/execution artifact를 연결해 사용한다.
- NF/R1/R2/R4는 R3와 동일한 output JSON schema를 사용한다.
- GT operation sequence, GT object/target, 정답 action은 어떤 prompt에도 제공하지 않는다.

---

## 5. 조건별 Prompt 정보 범위

모든 조건은 공통으로 다음 정보를 포함한다.

```text
original instruction
initial Qwen executor plan
allowed skill schema
allowed parameter schema
JSON-only output instruction
```

조건별 추가 정보는 다음과 같이 제한한다.

### NF. No-feedback Replan

포함:

```text
original instruction
initial Qwen executor plan
allowed output schema
```

제외:

```text
failure image
symptom log
executed trace
initial failure reason
```

목적:

```text
실패 정보를 주지 않고 다시 계획하게 했을 때의 순수 재질문 효과 측정
```

### R1. Symptom Log Only

포함:

```text
original instruction
initial Qwen executor plan
symptom log
allowed output schema
```

제외:

```text
failure/final image
executed trace
```

목적:

```text
텍스트 실패 증상만으로 recovery가 가능한지 측정
```

### R2. Failure Image Only

포함:

```text
original instruction
initial Qwen executor plan
failure/final image
allowed output schema
```

제외:

```text
symptom log
executed trace
```

목적:

```text
시각 실패 증거만으로 recovery가 가능한지 측정
```

### R3. Failure Image + Symptom Log

포함:

```text
original instruction
initial Qwen executor plan
failure/final image
symptom log
allowed output schema
```

목적:

```text
SILVER의 main configuration
```

### R4. Failure Image + Symptom Log + Executed Trace

포함:

```text
original instruction
initial Qwen executor plan
failure/final image
symptom log
executed trace summary
allowed output schema
```

목적:

```text
실행 trace까지 제공했을 때의 upper-bound 성능 확인
```

R4는 main method가 아니라 upper-bound ablation으로 해석한다. 실행 trace는 실제 시스템 내부 정보에 가까우므로, R4가 R3보다 높더라도 R3의 실용성이 약해지는 것은 아니다.

---

## 6. 실행 단위와 산출물 구조

결과 루트:

```text
C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\ablation_300
```

권장 구조:

```text
ablation_300\
  ABLATION_300_PROGRESS.md
  manifest\
    track_d_ablation_300_manifest.jsonl
    track_d_ablation_300_summary_by_status.csv
  data\
    <Category>\<task>\<example>\
      NF\
        prompt_NF.txt
        raw_output.json
        parsed_output.json
        adapter_validation.json
        executor_plan.json
      NF_execution\
        execution_result.json
        initial_mosaic.png
        final_mosaic.png
        orchestrator.log
      R1\
      R1_execution\
      R2\
      R2_execution\
      R4\
      R4_execution\
  metrics\
    ablation_300_inference_summary.csv
    ablation_300_execution_summary.csv
    ablation_300_condition_success_by_variant.csv
    ablation_300_failure_taxonomy_by_variant.csv
    ablation_300_pairwise_comparison.csv
    ablation_300_statistics.json
  report\
    TRACK_D_ABLATION_300_COMPLETION_REPORT.md
```

각 case와 각 variant에 대해 다음 artifact가 모두 있어야 완료로 인정한다.

```text
prompt
raw model response
parsed JSON
adapter validation
executor plan 또는 conversion failure record
execution result 또는 not_run_conversion_failed record
```

---

## 7. 실행 절차

### Step 1. Ablation subset manifest 생성

목표:

```text
Track D 1,040건 전체에서 C1/C2/C3/C4 비율을 고려한 300건 subset 생성
```

검증:

```text
총 300건인지 확인
C1=220, C2=60, C3=19, C4=1인지 확인
동일 seed로 재생성했을 때 동일 manifest가 나오는지 확인
```

### Step 2. NF/R1/R2/R4 prompt 생성

목표:

```text
각 variant별 정보 범위를 엄격히 분리한 prompt 생성
```

검증:

```text
NF prompt에 failure 정보가 들어가지 않았는지 확인
R1 prompt에 image가 들어가지 않았는지 확인
R2 prompt에 symptom log가 들어가지 않았는지 확인
R4 prompt에 executed trace가 포함됐는지 확인
모든 prompt에 GT answer가 포함되지 않았는지 확인
```

### Step 3. VLM inference 실행

대상:

```text
300건 x 4 variant = 1,200 calls
```

설정:

```text
model: Qwen/Qwen3-VL-8B-Instruct
temperature: 0
max_tokens: 1024
endpoint: http://127.0.0.1:8000/v1/chat/completions
```

검증:

```text
raw_output.json 1,200개 또는 명시적 inference_error.json 생성
parsed_output.json 생성
adapter_validation.json 생성
```

### Step 4. Executor plan 변환

목표:

```text
각 VLM output을 기존 Track D와 동일한 adapter로 executor plan으로 변환
```

검증:

```text
conversion_ok true/false 분리
conversion failure는 C2/C3/C4 계열로 기록
실행 불가능한 plan을 성공 처리하지 않음
```

### Step 5. Native execution 실행

대상:

```text
conversion_ok=True인 case만 실제 VLABench native execution 실행
conversion_ok=False인 case는 not_run_conversion_failed로 기록
```

검증:

```text
execution_result.json 생성
success=True/False/None 구분
native crash/timeout은 성공 처리 금지
```

### Step 6. 통계 및 paired comparison

각 300건 case는 다음 조건을 paired로 가진다.

```text
SR, NF, R1, R2, R3, R4
```

SR과 R3는 기존 전체 결과에서 300건 subset에 해당하는 결과를 가져온다. NF/R1/R2/R4는 새로 실행한다.

필수 지표:

```text
condition success rate
conversion success rate
execution attempted count
not_run_conversion_failed count
failure taxonomy count
```

필수 비교:

```text
R3 vs SR
R3 vs NF
R3 vs R1
R3 vs R2
R4 vs R3
```

통계:

```text
paired McNemar test: 주요 pairwise 비교
Cochran's Q: NF/R1/R2/R3/R4 전체 조건 성공률 비교
Holm-Bonferroni correction: 다중 비교 보정
bootstrap 95% CI: 각 조건 성공률과 gain
```

---

## 8. 논문 표 구성

### Main Table. Full Track D Recovery

전체 1,040건 사용.

| 조건 | 분모 | 성공 | 성공률 | 해석 |
|---|---:|---:|---:|---|
| R0 Initial Qwen | 1,040 | 0 | 0.00% | Track D failure set 정의상 초기 실패 |
| SR Same-plan retry | 1,040 | 36 | 3.46% | 단순 재시도 효과 |
| R3 SILVER | 1,040 | 326 | 31.35% | failure-aware replan |

주의:

- R0는 Track D가 실패 case로 구성되어 있으므로 0%로 해석한다.
- R0를 Track C 전체 2,133건 기준 성공률과 혼동하지 않는다.

### Ablation Table. Feedback Component Analysis

300건 subset 사용.

| 조건 | 제공 정보 | 성공 | 성공률 | R3 대비 |
|---|---|---:|---:|---:|
| NF | no feedback | TBD | TBD | TBD |
| R1 | symptom log only | TBD | TBD | TBD |
| R2 | failure image only | TBD | TBD | TBD |
| R3 | image + symptom log | 기존 결과에서 subset 추출 | TBD | 기준 |
| R4 | image + symptom + trace | TBD | TBD | TBD |

### Failure Taxonomy Table

각 variant별 C0/C1/C2/C3/C4/C5/C6 분포를 제시한다.

| 조건 | C0 success | C1 condition fail | C2 conversion fail | C3 entity fail | C4 unsupported | C5/C6 native issue |
|---|---:|---:|---:|---:|---:|---:|
| NF | TBD | TBD | TBD | TBD | TBD | TBD |
| R1 | TBD | TBD | TBD | TBD | TBD | TBD |
| R2 | TBD | TBD | TBD | TBD | TBD | TBD |
| R3 | TBD | TBD | TBD | TBD | TBD | TBD |
| R4 | TBD | TBD | TBD | TBD | TBD | TBD |

---

## 9. 논문 해석 기준

가능한 결과별 해석:

### R3 > NF

```text
실패 피드백이 없는 단순 재질문보다 failure-aware feedback이 유효하다.
```

### R3 > R1 and R3 > R2

```text
텍스트 또는 이미지 단일 정보보다, 두 정보를 결합한 multimodal failure feedback이 더 효과적이다.
```

### R1 > R2

```text
현재 benchmark에서는 명시적 실패 증상 텍스트가 시각 정보보다 더 직접적인 회복 단서를 제공한다.
```

### R2 > R1

```text
VLM은 실패 후 시각 상태에서 object/target 재선택 단서를 얻을 수 있다.
```

### R4 > R3

```text
실행 trace는 추가적인 upper-bound 정보를 제공하지만, R3는 trace 없이도 실용적인 회복 성능을 보인다.
```

### R4 ~= R3

```text
symptom log와 failure image만으로도 주요 회복 단서가 충분하며, trace 추가 효과는 제한적이다.
```

---

## 10. 금지 사항

다음은 금지한다.

```text
mock result 생성
실행하지 않은 case를 success로 기록
누락 artifact를 자동 성공 처리
GT operation sequence를 prompt에 포함
GT object/target을 prompt에 포함
성공 가능성이 높은 case만 수동 선택
conversion failure를 실행 성공/실패와 섞어 계산
```

모든 결과는 저장된 artifact에서 재계산 가능해야 한다.

---

## 11. 완료 기준

Track D ablation 완료 조건:

```text
300건 ablation manifest 생성 완료
NF/R1/R2/R4 각각 300건 inference 완료
NF/R1/R2/R4 각각 300건 execution 또는 not-run failure 기록 완료
R3 기존 결과에서 동일 300건 subset 추출 완료
SR 기존 결과에서 동일 300건 subset 추출 완료
variant별 success/failure taxonomy CSV 생성
paired comparison CSV 생성
통계 분석 JSON 생성
한국어 완료 보고서 작성
```

최종 완료 보고서:

```text
C:\SILVER\archive\silver_track_d_replanning_attribution_20260527\ablation_300\report\TRACK_D_ABLATION_300_COMPLETION_REPORT.md
```

보고서 필수 내용:

```text
실험 목적
subset 생성 기준
variant 정의
실행 환경
각 variant 성공률
R3 대비 gain
통계 검정 결과
failure taxonomy
대표 성공/실패 사례
논문에서 주장 가능한 범위
한계
```

---

## 12. 현재 기준 다음 작업

다음 구현 작업은 아래 순서로 진행한다.

1. `track_d_ablation_300_manifest.jsonl` 생성 스크립트 작성
2. NF/R1/R2/R4 prompt 생성 및 inference 함수 추가
3. NF/R1/R2/R4 execution 함수 추가
4. 기존 SR/R3 결과에서 300건 subset 결과 추출
5. ablation 통계 및 보고서 생성

