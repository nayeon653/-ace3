# Tax/Payout Agent 스펙

## 목적과 책임

Tax/Payout Agent는 연금 세액공제, 과세와 수령 조건을 제공 문서 근거로 판단한다.
검증된 입력이 있으면 Python Calculation Tool로 연금수령한도 또는 연금계좌 세액공제
대상액·세액을 계산한다(질문에 맞는 계산 Tool 하나만 호출).

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
`DomainResult`다. 계산을 실행한 결과에는 calculator ID, 정규화 입력, 출력, 단위와
warning이 `calculations`에 포함된다.

## Tool과 문서 접근

### `search_documents`

- `not_applicable` 판단 외에는 `submit_domain_result` 전에 반드시 한 번 호출해야 하며
  `pension_reference` 문서만 검색한다.
- 문서명과 청크 ID는 사용자 질문 원문에 실제 포함된 경우에만 힌트로 사용한다.
- 검색 방식과 결과 수는 Search Service가 결정한다.

### `calculate_pension_withdrawal_limit`

- 검색된 문서 근거가 있는 경우에만 실행한다.
- 입력은 원 단위 연금계좌 평가액과 1~10의 연금수령연차다.
- 사용자 질문 또는 검증된 검색 근거에 없는 입력을 추정하지 않는다.
- 각 입력에는 필드명, 그 값 하나와 단위가 포함된 원문 `source` 구절이 필요하다. Python은
  필드 의미, 질문 또는 검색 청크 포함 여부와 정규화 입력 일치를 검증한다. 검색 청크에서
  가져온 입력은 `chunk_id`를 계산 결과에 기록하고 최종 evidence에 자동 포함한다.
- Calculation Service의 `pension_withdrawal_limit`만 호출한다.
- 호출은 한 번으로 제한한다.

### `calculate_pension_tax_credit`

- 검색된 문서 근거가 있는 경우에만 실행한다.
- 필수 입력은 연금저축 순납입액과 퇴직연금 순납입액(각각 원 단위)이며, 각 입력에는
  필드명·값 하나·`원` 단위가 포함된 원문 `source` 구절이 필요하다.
- 선택 입력(ISA 만기자금 전환액 2종, 전년도 동일 만기자금 추가 공제대상액 사용분,
  소득 기준·소득금액, 잔여 산출세액)은 값과 `source`가 모두 있을 때만 함께 전달하고
  하나만 있으면 호출하지 않는다.
- 소득 기준(`income_basis`)의 `source`는 `총급여` 또는 `종합소득금액` 표현을, 소득금액의
  `source`는 `income_basis`와 같은 표현을 포함해야 한다. ISA 관련 선택 입력의 `source`는
  `전년도` 표현을 포함해야 한다.
- 출력은 `regular_eligible_contribution_krw`, `isa_extra_remaining_cap_krw`,
  `isa_extra_limit_krw`, `isa_extra_eligible_contribution_krw`,
  `eligible_contribution_krw`이며, 소득 기준이 있으면 `credit_rate_percent`·
  `theoretical_credit_krw`(잔여 산출세액이 있으면 `usable_credit_krw` 포함)를, 없으면
  `lower_income_rate_percent`·`lower_income_theoretical_credit_krw`·
  `other_income_rate_percent`·`other_income_theoretical_credit_krw`를 함께 반환한다.
- `usable_credit_krw`는 잔여 산출세액 기준 사용 가능한 세액이며 실제 환급액이 아니다.
- Calculation Service의 `pension_tax_credit`만 호출한다.
- 호출은 한 번으로 제한하며, `calculate_pension_withdrawal_limit`과 같은 실행에서 함께
  호출하지 않는다(질문에 맞는 계산 Tool 하나만 선택).

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
       -> 연금수령한도 질문이고 입력이 충분하면 calculate_pension_withdrawal_limit 1회,
          연금계좌 세액공제 질문이고 입력이 충분하면 calculate_pension_tax_credit 1회
          (질문에 맞는 계산 Tool 하나만 호출)
       -> submit_domain_result(계산 없이 conclusion에 확정 수치가 있으면 비수치 재제출 1회 요청)
     )
  -> 검증된 DomainResult
```

- 검색 결과에 없는 제도, 조건과 수치를 생성하지 않는다.
- 문서에 수치가 있더라도 이를 사용자 조건에 대한 확정 계산값으로 변환하지 않는다.
- 조건·정성적 비교 질문은 확정 수치 없이 근거 기반 설명을 허용한다.
- 계산 입력의 원문 구절을 검증할 수 없으면 숫자를 생성하지 않는다.
- Tool이 지원하는 연금수령한도만 확정 계산하며 Python 결과로 결론을 교체한다.
- 지원하지 않는 계산이나 입력이 부족한 질문은 `conditional` 또는 `undetermined`로
  판단하고 필요한 입력(또는 계산 Tool 부재)을 누락 조건으로 남긴다.
- 복합 질문에서 연금수령한도만 계산되더라도 미계산 항목이 있으면 전체 상태와 누락 조건을
  보존한다.
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
| 연금수령한도 Tool | 최대 1회 |
| 연금 세액공제 Tool | 최대 1회 |
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

## 현재 제한

- 현재 연결된 계산기는 연금수령한도와 연금계좌 세액공제 두 개다.
- 연금소득세율 계산기는 구현·연결하지 않았다.
- 계산 근거 문서의 파일명·페이지 매핑은 `docs/specs/components/calculation-service.md`
  에서 관리한다(이 문서에는 중복 기록하지 않는다).
- 계산 근거 청크를 최종 결과에 제출하지 않으면 실행된 계산도 최종 `calculations`에서
  제거한다.

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `notebooks/agent/tax_payout_agent_playground.ipynb`
