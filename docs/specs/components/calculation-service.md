# Calculation Service 스펙

## 목적과 책임

Calculation Service는 원문 대조를 마친 소수의 계산 규칙을 결정론적 Python 함수로
실행한다. LLM, 검색, 문서 파서와 Agent adapter를 포함하지 않는다.

```text
CalculationRequest { calculator_id, inputs }
  -> CALCULATORS에서 명시적 함수 조회
  -> 계산기별 Pydantic 입력 검증
  -> Python 함수 실행
  -> CalculationResult
```

현재 확장 지점은 `pension_agent.rules.calculators.CALCULATORS` 딕셔너리 하나다. 동적 등록,
lifecycle, 다중 버전 선택, 적용 기간과 계산 permission은 구현하지 않는다.

## 요청과 결과

`CalculationRequest`는 다음 필드만 허용한다.

| 필드 | 설명 |
|---|---|
| `calculator_id` | `CALCULATORS`의 snake_case 계산기 ID |
| `inputs` | 계산기별 Pydantic 입력 모델에 전달할 값 |

`CalculationResult`는 다음 내용을 반환한다.

- 계산기 ID
- Pydantic이 정규화한 입력
- 출력 키별 값과 단위
- 계산 결과 사용 시 확인해야 할 warning

금액과 비율은 `Decimal`로 계산하고 JSON에서는 문자열로 직렬화한다. 계산 출처는 현재
결과와 Agent의 `evidence`에 포함하지 않는다. PDF와 formula catalog는 오프라인 산식 검증
자료로만 관리한다.

## 등록된 계산기

| 계산기 ID | 산식·규칙 | 검증 문서 |
|---|---|---|
| `pension_withdrawal_limit` | 평가액 ÷ (11 - 수령연차) × 120%, 1~10년차 | `doc2.pdf` 1쪽 |
| `fund_standard_price` | (자산총액 - 부채총액) ÷ 총좌수 × 1,000, 소수 셋째 자리 반올림 | `R2_KR510902511M.pdf` 24쪽 |
| `fund_var_risk` | `abs(일간 2.5퍼센타일 손실률) × √250` 후 6단계 상한표 | `R2_KR5160420009.pdf` 20쪽 |

검증 문서 정보는 개발 기록이며 런타임 결과에 직렬화하지 않는다. 문서에 없는 표시
자릿수나 최종 지급 단위 반올림은 임의로 적용하지 않고 warning에 남긴다.

## 실행 제한과 오류

- 문자열 수식, DSL, `eval`과 동적 모듈 import를 실행하지 않는다.
- 계산 함수는 네트워크, 파일, 현재 시간, 난수와 환경변수를 읽지 않는다.
- `rules`는 `agent`, `retrieval`, `ingest`를 import하지 않는다.

| 오류 | 조건 |
|---|---|
| `CalculatorNotFoundError` | 계산기 ID가 등록되지 않음 |
| `InvalidCalculationInputError` | Pydantic 입력 검증 실패 |
| `CalculationExecutionError` | 검증 후 산술 조건을 만족하지 못함 |

입력 오류는 필드 경로와 Pydantic 오류 코드만 보존하며 원시 입력값을 오류 문자열에 넣지
않는다.

## 계산 함수 추가

1. 원본 PDF 또는 제공 문서에서 산식, 변수, 조건, 단위와 반올림을 직접 대조한다.
2. `extra="forbid"`, `frozen=True`인 Pydantic 입력 모델을 작성한다.
3. 입력 모델 하나를 받아 `CalculationOutput`을 반환하는 순수 Python 함수를 작성한다.
4. `CalculatorDefinition`을 만들고 `CALCULATORS`에 계산기 ID 한 항목을 추가한다.
5. 정상값, 경계값, 잘못된 입력, 반올림과 결정성 테스트를 추가한다.

## Agent 연결 경계

Calculation Service에는 Agent permission 계층을 넣지 않는다. Agent 계층이 계산기별로
명시적인 Tool schema를 만들고 실제 전달한 Tool만 호출할 수 있게 한다.

| 소비자 | 허용 계산기 |
|---|---|
| Tax/Payout Agent | `pension_withdrawal_limit` |
| Product Agent | `fund_standard_price`, `fund_var_risk` |
| Policy Agent | 없음 |
| Main Supervisor | 직접 호출 금지 |

Calculation Tool은 완료된 검색 근거가 있어야 실행되고 결과를 Agent state에 직접 누적한다.
최종 `DomainResult`에 근거 청크가 없으면 계산 결과도 제거한다. `AnswerService`는 계산만 있는
답변을 검증된 Python 결과로 교체하고 복합 답변에는 같은 결과를 결정론적으로 덧붙인다.

## 검증 위치

- `tests/unit/rules/test_calculation_service.py`
- `tests/unit/rules/test_initial_calculators.py`
- `tests/test_agent_import_boundaries.py`
