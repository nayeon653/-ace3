# Tax/Payout Agent 스펙

## 목적과 책임

Tax/Payout Agent는 연금 세액공제, 과세와 수령 조건을 제공 문서 근거로 판단한다.
검증된 평가액과 수령연차가 있으면 Python Calculation Tool로 연금수령한도를 계산한다.

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
`DomainResult`다. 계산을 실행한 결과에는 calculator ID, 정규화 입력, 출력, 단위와
warning이 `calculations`에 포함된다.

## Tool과 문서 접근

### `search_documents`

- 한 번 호출하며 `pension_reference` 문서만 검색한다.
- 문서명과 청크 ID는 사용자 질문 원문에 실제 포함된 경우에만 힌트로 사용한다.
- 검색 방식과 결과 수는 Search Service가 결정한다.

### `calculate_pension_withdrawal_limit`

- 검색된 문서 근거가 있는 경우에만 실행한다.
- 입력은 원 단위 연금계좌 평가액과 1~10의 연금수령연차다.
- 사용자 질문 또는 검증된 검색 근거에 없는 입력을 추정하지 않는다.
- Calculation Service의 `pension_withdrawal_limit`만 호출한다.
- 호출은 한 번으로 제한한다.

### `submit_domain_result`

모델은 검색 후 판단 상태, 결론, 누락 조건, 경고와 실제 사용한 청크 ID만 제출한다.
Python은 청크 ID의 UUID 형식, 중복과 SearchResult 부분집합 여부를 검증한다.

## 실행 흐름과 안전 규칙

```text
DomainRequest
  -> search_documents 1회
  -> 검색 실패/timeout/빈 결과면 Python 안전 종료
  -> 연금수령한도 질문이고 입력이 충분하면 calculate_pension_withdrawal_limit 1회
  -> submit_domain_result
  -> 검증된 DomainResult
```

- 검색 결과에 없는 제도, 조건과 수치를 생성하지 않는다.
- Tool이 지원하는 연금수령한도만 확정 계산하며 Python 결과로 결론을 교체한다.
- 지원하지 않는 계산이나 입력이 부족한 질문은 `conditional` 또는 `undetermined`로
  판단하고 필요한 입력을 누락 조건으로 남긴다.
- 근거 ID가 없으면 `not_applicable` 이외의 판단을 `undetermined`로 보정한다.
- 검색 제한사항은 `warnings`에 포함한다.

## 실행 제한

| 제한 | 값 |
|---|---:|
| 모델 호출 | 최대 5회 |
| 검색 Tool | 최대 1회 |
| 연금수령한도 Tool | 최대 1회 |
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

## 현재 제한

- 현재 연결된 계산기는 연금수령한도 하나다.
- 세액공제와 연금소득세율 계산기는 구현·연결하지 않았다.
- 계산 근거 청크를 최종 결과에 제출하지 않으면 실행된 계산도 최종 `calculations`에서
  제거한다.

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `notebooks/agent/tax_payout_agent_playground.ipynb`
