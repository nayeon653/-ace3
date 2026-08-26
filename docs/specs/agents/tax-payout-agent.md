# Tax/Payout Agent 스펙

## 목적과 책임

Tax/Payout Agent는 연금 세액공제, 과세와 수령 조건을 제공 문서 근거로 판단한다. 현재
구현은 문서 근거에 따른 조건 판단까지만 수행하며 사용자 조건을 적용한 확정 세금·금액
계산은 수행하지 않는다.

## 모델과 구현

| 항목 | 값 |
|---|---|
| 구현 | 독립 `create_agent` 기반 ReAct graph |
| 모델 | `HCX-005` |
| temperature / 최대 토큰 | `0.1` / `1024` |
| Provider timeout/retry | 호출당 30초, 최대 2회 retry |
| 프롬프트 | `pension_agent/prompts/domain/tax-payout-agent.md` |
| 구현 | `pension_agent/agent/tax_payout/` |

## 입력과 출력

입력은 `DomainRequest {question, objective}`다. 출력은 `domain=tax_payout`인 공통
`DomainResult`다. 현재 모든 결과의 `calculations`는 빈 목록이다.

## Tool과 문서 접근

### `search_documents`

- 한 번 호출하며 `pension_reference` 문서만 검색한다.
- 문서명과 청크 ID는 사용자 질문 원문에 실제 포함된 경우에만 힌트로 사용한다.
- 검색 방식과 결과 수는 Search Service가 결정한다.

### `submit_domain_result`

모델은 검색 후 판단 상태, 결론, 누락 조건, 경고와 실제 사용한 청크 ID만 제출한다.
Python은 청크 ID의 UUID 형식, 중복과 SearchResult 부분집합 여부를 검증한다.

## 실행 흐름과 안전 규칙

```text
DomainRequest
  -> search_documents 1회
  -> 검색 실패/timeout/빈 결과면 Python 안전 종료
  -> submit_domain_result
  -> 검증된 DomainResult(calculations=[])
```

- 검색 결과에 없는 제도, 조건과 수치를 생성하지 않는다.
- 문서에 수치가 있더라도 이를 사용자 조건에 대한 확정 계산값으로 변환하지 않는다.
- 확정 계산이 필요한 질문은 `conditional` 또는 `undetermined`로 판단하고 필요한 입력과
  계산 Tool 부재를 누락 조건 또는 경고에 남긴다.
- 근거 ID가 없으면 `not_applicable` 이외의 판단을 `undetermined`로 보정한다.
- 검색 제한사항은 `warnings`에 포함한다.

## 실행 제한

| 제한 | 값 |
|---|---:|
| 모델 호출 | 최대 5회 |
| 검색 Tool | 최대 1회 |
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

## 현재 제한

`pension_agent/rules/`에는 Agent와 분리된 공용 Calculation Service와 일부 초기 계산
함수가 구현되어 있다. 다만 Tax/Payout Agent의 계산 Tool과 결과 연결은 아직 구현하지
않았다. 따라서 공통 계약에 `CalculationResult`가 정의되어 있어도 현재 Tax/Payout Agent는
이를 생성하지 않는다.

계산 기능을 추가할 때는 다음을 같은 변경에서 명세해야 한다.

1. 계산기 이름과 기준 연도
2. 필수 입력, 단위와 허용 범위
3. 조건 누락·경계값·오류 처리
4. 문서 근거와 계산 결과의 연결
5. `CalculationResult` 직렬화와 회귀 테스트

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `notebooks/agent/tax_payout_agent_playground.ipynb`
