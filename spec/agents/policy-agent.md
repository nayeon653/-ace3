# Policy Agent 스펙

## 목적과 책임

Policy Agent는 연금 가입, 이전, 해지, 수령 절차와 제도상 가능 여부를 제공 문서 근거로
판단한다. 세액·세율의 확정 계산과 개별 펀드의 비용·위험 판단은 수행하지 않는다.

## 모델과 구현

| 항목 | 값 |
|---|---|
| 구현 | 독립 `create_agent` 기반 ReAct graph |
| 모델 | `HCX-005` |
| temperature / 최대 토큰 | `0.1` / `1024` |
| Provider timeout/retry | 호출당 30초, 최대 2회 retry |
| 프롬프트 | `pension_agent/prompts/domain/policy-agent.md` |
| 구현 | `pension_agent/agent/policy/` |

## 입력과 출력

입력은 `DomainRequest {question, objective}`다. `objective`는 하나의 업무·제도 판단이어야
한다. 출력은 공통 `DomainResult`이며 `domain`은 항상 `policy`다.

완료 결과는 판단 상태, 결론, 누락 조건, 실제 사용 근거와 경고를 포함한다.
`calculations`는 항상 빈 목록이다.

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

## 실행 흐름

```text
DomainRequest
  -> search_documents 1회
  -> 검색 실패/timeout/빈 결과면 Python 안전 종료
  -> 검색 근거가 있으면 submit_domain_result
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
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

호출 상한까지 검증된 결과가 제출되지 않으면 공통 Runner가 이를 정제된 실패 결과로
변환한다.

## 현재 제한

- 제도 문서 사이의 상충 claim을 별도 Validator가 판정하지 않는다.
- 수치 계산 Tool을 갖지 않는다.
- 결과 품질은 검색된 `pension_reference` 청크 범위에 한정된다.

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `notebooks/agent/policy_agent_playground.ipynb`
