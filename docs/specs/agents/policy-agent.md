# Policy Agent 스펙

## 목적과 책임

Policy Agent는 연금 가입, 이전, 해지, 수령 절차와 제도상 가능 여부를 제공 문서 근거로
판단한다. 세액·세율의 확정 계산과 개별 펀드의 비용·위험 판단은 수행하지 않는다.

## 모델과 구현

| 항목 | 값 |
|---|---|
| 구현 | 독립 `create_agent` 기반 ReAct graph |
| 모델 | `HCX-007`, Thinking `none` (후보) |
| temperature / 최대 토큰 | `0.1` / `1024` |
| Provider timeout/retry | 호출당 30초, 최대 2회 retry |
| 프롬프트 | `pension_agent/prompts/domain/policy-agent.md` |
| 구현 | `pension_agent/agent/policy/` |

Policy만 상위 모델로 분리한 이유와 채택 조건은
[`Policy Agent에 HCX-007 비추론 모델을 분리 적용하는 후보`](../../decisions/20260905-policy-agent-hcx-007-candidate.md)에
기록한다. 현재 제안 상태이므로 기존 역할별 모델 결정과 프로젝트 공통 규칙을 대체하지
않는다.

## 입력과 출력

입력은 `DomainRequest {question, objective}`다. `objective`는 하나의 업무·제도 판단이어야
한다. 출력은 공통 `DomainResult`이며 `domain`은 항상 `policy`다.

완료 결과는 판단 상태, 결론, 누락 조건, 실제 사용 근거와 경고를 포함한다.
`calculations`는 Policy가 허용한 DC 의료비 threshold 또는 ISA 연금전환 기한 계산 결과와
검증된 input source를 포함할 수 있다.

## Tool과 문서 접근

### `search_documents`

- 한 번 호출한다.
- `pension_reference` 문서만 검색할 수 있다.
- 입력은 `objective`, 선택적 `source_file_name`, `chunk_id`, `expand_neighbors`다.
- 문서명과 청크 ID는 사용자 질문 원문에 실제 포함된 경우에만 힌트로 허용한다.
- 검색 모드, 후보 수, cutoff는 Agent가 정하지 않고 Search Service가 관리한다.

### `submit_domain_result`

검색 후 자유 형식 답변 대신 이 Tool을 호출한다. 모델은 `status`, `conclusion`,
`missing_conditions`, `warnings`, `evidence_chunk_ids`를 제출한다. Python은 청크 ID가 검색
결과의 중복 없는 부분집합인지 검증하고 원문 `EvidenceChunk`로 변환한다.

### `calculate_isa_transfer_deadline`

- ISA 만기자금의 연금계좌 전환 마감일과 선택적인 60일 기한 충족 여부에만 사용한다.
- Policy는 질문이 deadline-only인지 완료 여부 판정인지 구분하고, ISA 만기일과
  입금확인·전환완료 처리일의 의미를 확인한다.
- 신청일·접수일·단순 입금일·의미가 불명확한 처리일을 완료일로 승격하지 않는다.
- Tool은 실행당 최대 1회이며 성공 뒤에는 submit만 허용한다.

## 실행 흐름

```text
DomainRequest
  -> search_documents 1회
  -> 검색 실패/timeout/빈 결과면 Python 안전 종료
  -> 필요한 경우 허용된 Calculation Tool 1회
  -> 검색 근거와 선택적인 계산 결과로 submit_domain_result
  -> 검증된 DomainResult
```

- 검색 실패와 timeout은 같은 상태의 실패 `DomainResult`로 종료한다.
- 검색은 완료됐지만 청크가 없으면 `undetermined`로 종료한다.
- 모델이 근거 ID를 제출하지 않으면 `not_applicable`이 아닌 판단은 `undetermined`로
  보정한다.
- `not_applicable`이면 결론, 누락 조건, 경고와 근거를 정해진 빈 상태로 정규화한다.
- 검색 제한사항은 최종 `warnings`에 합친다.

## 판단 상태

| 상태 | 사용 조건 |
|---|---|
| `determined` | 근거가 충분하고 사용자 조건 누락이 없음 |
| `conditional` | 명시된 조건에 따라 결론이 달라짐 |
| `undetermined` | 제공 문서 근거 또는 필수 조건이 부족함 |
| `not_applicable` | 요청한 판단이 Policy 책임에 해당하지 않음 |

`conditional`과 `undetermined`에는 구체적인 `missing_conditions`가 필요하다. 질문에 없는
가입 유형, 계좌 상태 또는 사용자 속성을 추정하지 않는다.

## 실행 제한

| 제한 | 값 |
|---|---:|
| 모델 호출 | 최대 5회 |
| 검색 Tool | 최대 1회 |
| DC 의료비 threshold Tool | 최대 1회 |
| ISA 연금전환 기한 Tool | 최대 1회 |
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

호출 상한까지 검증된 결과가 제출되지 않으면 공통 Runner가 이를 정제된 실패 결과로
변환한다.

## 현재 제한

- 제도 문서 사이의 상충 claim을 별도 Validator가 판정하지 않는다.
- ISA 연금전환 기한의 현재 기준 남은 일수는 검증된 reference date 입력 계약이 없어
  계산하지 않는다.
- 결과 품질은 검색된 `pension_reference` 청크 범위에 한정된다.

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `notebooks/agent/policy_agent_playground.ipynb`

## DC 의료비 threshold 계산

- Policy Agent가 DC/IRP, 6개월 이상 요양, 가족관계와 서류·증빙 적정성을 판단한다.
- DC의 검증된 범주형 재직기간·임금·의료비 입력은 `calculate_dc_medical_withdrawal_threshold`에 전달한다.
- Tool은 실행당 최대 1회이며 성공 뒤에는 submit만 허용한다. 계산과 submit은 같은 model call에서 분리한다.
- 계산 결과, input source와 evidence를 `DomainResult.calculations` 및 `evidence`에 보존한다.
- threshold 결과는 최종 eligibility가 아니다. 법적 요건 확인이 제출되지 않으면 Python 경계가 최소 `conditional`을 강제한다.
- IRP에는 DC threshold Tool을 호출하지 않으며 12.5% 예외만으로 최종 가능 여부를 확정하지 않는다.

## DB·DC 퇴직급여 제도 판단

- Policy는 DB/DC 제도 유형, 평균임금 제외기간, 계속근로·근속 인정 여부, 검증된 근속연수의 사용 가능성과 DB→DC 전환 자격·조건·절차를 판단한다.
- 제도 유형, 근속 인정 또는 전환 가능 조건이 미확정이면 각각 `DB 또는 DC 제도 유형 확인 필요`, `계속근로·근속 인정 여부 확인 필요`, `DB→DC 전환 가능 조건 확인 필요`를 조건으로 보존한다.
- 평균일급, 30일 평균임금, 퇴직급여, 최소 사용자 부담금, 전환금액과 퇴직소득세 계산은 Tax/Payout 책임이다.
- Policy는 #118 Calculation Tool을 등록하지 않으며, 전환금액 결과를 전환 가능 여부로 해석하거나 검증되지 않은 기간·근속연수를 생성하지 않는다.

## ISA 만기자금 연금전환 기한

- Policy는 요청이 마감일 계산인지 실제 완료일의 기한 충족 판정인지 구분하고, 기준일이
  ISA 만기일인지 확인한다. Calculation Service는 검증된 날짜의 60 calendar days 산술과
  선택적인 완료일 비교만 담당한다.
- 완료 판정에는 입금확인 완료일 또는 연금전환 완료 처리일만 사용한다. 신청일, 접수일,
  단순 입금일, 해지일, 계약일과 문서 작성일은 각 날짜 의미를 대체하지 않는다.
- 만기일만 확인된 완료 여부 질문은 계산 가능한 마감일을 보존하면서
  `입금확인·전환완료 처리일 확인 필요`인 `conditional`로 제출한다. 만기일 자체가 없으면
  `ISA 만기일 확인 필요`를 기록한다.
- `within_deadline`은 60일 기한만 판정하며 전체 ISA 연금전환 eligibility를 확정하지 않는다.
  전체 가능 여부 질문에는 나머지 적용 요건을 별도로 확인한다.
- 현재 시간을 읽지 않는다. 오늘 기준 남은 일수 요청은 마감일만 계산하고 검증된 기준일을
  누락 조건으로 남긴다.
