# Main Supervisor 스펙

## 목적과 책임

Main Supervisor는 `GET /answer`의 질문을 독립적인 비즈니스 판단으로 나누고 필요한 Domain
Agent만 Tool로 호출한 뒤, 검증된 도메인 결론을 한국어 최종 답변으로 통합한다.

Main Supervisor는 문서를 직접 검색하거나 세금·금액을 계산하지 않는다. Domain Agent가
반환하지 않은 근거, 조건, 수치와 상품 정보를 생성하지 않는다.

## 모델과 구현

| 항목 | 값 |
|---|---|
| 구현 | LangChain `create_agent` 기반 ReAct graph |
| 모델 | `HCX-007` |
| Thinking | `none` |
| temperature | `0.1` |
| 최대 생성 토큰 | `1024` |
| Provider timeout/retry | 호출당 30초, 최대 2회 retry |
| 프롬프트 | `pension_agent/prompts/orchestration/main-supervisor.md` |
| 구현 | `pension_agent/agent/orchestration/supervisor.py` |

## 입력과 상태

초기 상태는 다음 값을 가진다.

| 필드 | 설명 |
|---|---|
| `question_id` | 요청에서 받은 질의 ID |
| `question` | 요약하거나 조건을 추가하지 않은 질문 원문 |
| `messages` | 질문 원문을 담은 대화 메시지 |
| `domain_results` | 실행된 전체 `DomainResult`의 누적 목록 |

Tool 호출에서 모델이 생성하는 인자는 `objective` 하나다. Tool Adapter가 원문 `question`을
신뢰 상태에서 결합하므로 모델이 사용자 질문을 임의로 다시 쓰거나 조건을 추가한 값을
Domain Agent 입력으로 사용할 수 없다.

## Domain Tool과 라우팅

| Tool | 호출 기준 | Domain 문서 권한 |
|---|---|---|
| `analyze_policy` | 가입, 이전, 해지, 수령 절차와 제도상 가능 여부 | `pension_reference` |
| `analyze_tax_payout` | 세액공제, 과세, 연금 수령 조건 | `pension_reference` |
| `analyze_product` | 상품 카탈로그, 개별 상품 특성·비용·위험·유동성 | `fund_prospectus` 및 상품 카탈로그 |

- 하나의 Tool 호출에는 하나의 구체적인 판단만 넣는다.
- 복합 질문은 판단 단위로 나누어 여러 Tool을 호출할 수 있다.
- 서로 독립적인 Tool 호출은 한 모델 응답에서 함께 생성해 병렬 실행할 수 있다.
- 같은 판단을 탐색적으로 반복하지 않는다. 같은 Domain에 서로 다른 판단이 있으면 별도
  `objective`로 호출할 수 있다.
- 비교 기준이 없는 계좌·제도 비교는 Policy와 Tax/Payout을 함께 사용한다.
- 구체적인 펀드·펀드 클래스의 특성 비교는 Product를 사용한다.

## Domain Tool 결과

Main 모델에는 전체 근거나 계산 내역을 제외한 `DomainToolResult`만 전달한다.

- `domain`
- `execution_status`
- `decision`(완료 시)
- `warnings`
- `catalog_result`(상품 카탈로그 조회 시)
- `error`(실패 또는 timeout 시)

전체 `DomainResult`는 `SupervisorState.domain_results`에 별도로 누적되며 API의
`retrieved_context`와 `think_trace` 조립에 사용된다.

## 최종 답변

- 마지막 Tool 결과가 도착한 뒤 자연어 `AIMessage` 하나를 생성한다.
- 한국어로 결론, 확인이 필요한 조건, 경고 순서로 설명한다.
- 조건이 부족해도 되묻지 않고 조건별 결론을 한 응답에 포함한다.
- 실패하거나 timeout인 Domain의 결론을 추정하지 않고 가용 결과와 한계를 설명한다.
- `catalog_result`의 개수, 공식 상품명, 운용사와 상품 코드를 변경하거나 추정하지 않는다.
- JSON과 Tool 호출 형식을 사용자 답변으로 출력하지 않는다.

마지막 Tool 호출이 없는 자연어 `AIMessage`가 없으면 `AgentAnswer` 변환은 실패하며 API는
정제된 서버 오류로 처리한다.

## 실행 제한과 실패 처리

| 제한 | 값 |
|---|---:|
| 한 요청의 Supervisor 모델 호출 | 최대 12회 |
| 각 Domain Tool 호출 | Tool별 최대 3회 |
| 전체 요청 deadline | 180초 |

Domain Tool Adapter는 Runner 예외, 잘못된 결과 또는 Domain 불일치를 로그에 남기고
`execution_status=failed`인 정제 결과로 변환한다. 원시 예외, stack trace, 내부 주소와
모델 내부 메시지는 응답에 포함하지 않는다.

## 현재 범위 밖

- 명시적 Python Router와 사용자 조건 추출 노드
- 여러 Domain 결과의 충돌을 판정하는 Result Aggregator
- 답변 claim과 evidence의 의미 연결을 검사하는 Evidence Validator
- Domain별 자동 재시도·재라우팅
- 장기 메모리, 사용자 프로필과 로그인 상태

## 검증 위치

- `tests/unit/agent/orchestration/test_supervisor.py`
- `tests/unit/agent/orchestration/test_service.py`
- `tests/unit/agent/test_agent_contracts.py`
- `tests/test_agent_graph_document.py`
