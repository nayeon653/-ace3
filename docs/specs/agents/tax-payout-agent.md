# Tax/Payout Agent 스펙

## 목적과 책임

Tax/Payout Agent는 연금 세액공제, 과세와 수령 조건을 제공 문서 근거로 판단한다. 현재
구현은 문서 근거에 따른 조건 판단까지만 수행하며 사용자 조건을 적용한 확정 세금·금액
계산은 수행하지 않는다.

세액공제 적용 조건, 연금 과세, 수령 방식(일시금/분할)에 따른 과세, 중도해지 과세는 이
Agent의 책임이다. 상품의 위험·비용·수익률은 Product, 계좌 이전·가입·해지 절차 자체는
Policy 책임이며 이 Agent는 해당 질문을 `not_applicable`로 제출한다(중도해지로 발생하는
과세 판단 자체는 예외로 이 Agent 책임에 남는다).

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

- `not_applicable` 판단 외에는 `submit_domain_result` 전에 반드시 한 번 호출해야 하며
  `pension_reference` 문서만 검색한다.
- 문서명과 청크 ID는 사용자 질문 원문에 실제 포함된 경우에만 힌트로 사용한다.
- 검색 방식과 결과 수는 Search Service가 결정한다.

### `submit_domain_result`

`status="not_applicable"`은 검색 없이 바로 제출할 수 있다 — Product·Policy 책임
질문을 즉시 위임하기 위함이며, 결론·누락 조건·경고·evidence는 항상 빈 상태로
정규화된다. 그 외 상태(`determined`/`conditional`/`undetermined`)는 여전히
`search_documents`를 먼저 호출해야 하며, 모델은 판단 상태, 결론, 누락 조건, 경고와
결론에 실제 사용한 최소 청크 ID만 제출한다. 검색된 청크 전체를 그대로 제출하지
않는다. Python은 청크 ID의 UUID 형식, 중복과 SearchResult 부분집합 여부를
검증한다.

## 실행 흐름과 안전 규칙

```text
DomainRequest
  -> not_applicable ? submit_domain_result(검색 없이 즉시 정규화) : (
       search_documents 1회
       -> 검색 실패/timeout/빈 결과면 Python 안전 종료
       -> submit_domain_result(conclusion에 확정 수치가 있으면 비수치 재제출 1회 요청)
     )
  -> 검증된 DomainResult(calculations=[])
```

- 검색 결과에 없는 제도, 조건과 수치를 생성하지 않는다.
- 문서에 수치가 있더라도 이를 사용자 조건에 대한 확정 계산값으로 변환하지 않는다.
- 조건·정성적 비교 질문은 확정 수치 없이 근거 기반 설명을 허용한다.
- 확정 계산이 필요한 질문은 `conditional`로 판단하고 필요한 입력과 계산 Tool 부재를
  누락 조건 또는 경고에 남긴다.
- 근거 ID가 없으면 `not_applicable` 이외의 판단을 `undetermined`로 보정한다.
- 검색 제한사항은 `warnings`에 포함한다.
- 숫자 차단 후처리는 결론·누락 조건·경고를 필드별로 각각 검사하며, 실제 숫자·%·퍼센트·
  금액 단위가 포함된 필드만 대상으로 한다. `세율`·`한도`·`금액`·`공제액` 같은 화제어만으로는
  적용하지 않는다.
- 결론 자체에 확정 수치가 없다면 누락 조건이나 경고 중 일부에 숫자가 섞여 있어도 결론과
  상태는 그대로 두고, 숫자가 포함된 누락 조건·경고 항목만 제거한다(비수치 항목은 보존).
  이 경우 근거 없는 수치를 제거했다는 사실만 별도 경고로 남기며, 계산 Tool 필요 경고는
  추가하지 않는다. `conditional`에서 이 필터링으로 누락 조건이 하나도 안 남으면
  `결정론적 계산 Tool 결과`가 아니라 "판단에 필요한 사용자 조건"과 같은 일반 사용자
  조건 fallback을 넣는다 — 나이·가입기간 같은 일반 조건 누락을 계산 문제로 왜곡하지
  않기 위함이다.
- 결론 자체에 확정 수치가 있을 때만 `determined`/`conditional`을 계산 Tool 필요
  `conditional` 결과로 교체한다(결론·누락 조건·계산 Tool 필요 경고를 표준 문구로 통일).
- `undetermined`(근거 부족)는 숫자 차단으로 어떤 경우에도 `conditional`로 승격하지
  않는다 — "근거 부족"과 "계산 필요"는 의미가 다르다. 결론에 확정 수치가 있으면 비수치
  근거 부족 문구로만 교체하고, 기존 비수치 누락 조건은 유지한다. 비수치 누락 조건이 하나도
  남지 않을 때만 일반 근거 부족 조건을 넣는다. 계산 Tool 필요 누락 조건이나 경고는
  추가하지 않고, 근거 없는 수치를 제거했다는 별도 경고만 남긴다.
- `not_applicable` 제출은 숫자 차단 대상에서 제외한다. 결론·누락 조건·경고·evidence는
  항상 빈 상태로 정규화된다.
- 결론 자체에 확정 수치가 있으면 그 제출을 즉시 최종 결과로 확정하지 않고, 숫자 없이
  다시 제출하라는 안내와 함께 정확히 1회 재제출 기회를 준다. 재제출된 결론에 수치가
  없으면 그대로 받아들인다. 재제출도 수치를 포함하면 더 이상 기회를 주지 않고 위 숫자
  차단 후처리(표준 계산기 문구 치환 또는 `undetermined` 비수치 보정)로 확정한다. 이
  재제출 판단은 결론 필드만 대상으로 하며, 누락 조건·경고에만 숫자가 있는 경우는
  필드별 제거만 적용하고 재제출을 요구하지 않는다. 재제출 1회는 기존 `제출 Tool 최대
  2회` 한도 안에서 소비되며 별도 한도를 추가하지 않는다.

## 실행 제한

| 제한 | 값 |
|---|---:|
| 모델 호출 | 최대 5회 |
| 검색 Tool | 최대 1회 |
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

## 현재 제한

`pension_agent/rules/`에는 아직 세액공제, 연금소득세율, 연금수령한도 등의 결정론적
계산기와 Agent Tool 연결이 구현되어 있지 않다. 따라서 공통 계약에 `CalculationResult`가
정의되어 있어도 현재 Tax/Payout Agent는 이를 생성하지 않는다.

계산 기능을 추가할 때는 다음을 같은 변경에서 명세해야 한다.

1. 계산기 이름과 기준 연도
2. 필수 입력, 단위와 허용 범위
3. 조건 누락·경계값·오류 처리
4. 문서 근거와 계산 결과의 연결
5. `CalculationResult` 직렬화와 회귀 테스트

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `notebooks/agent/tax_payout_agent_playground.ipynb`
