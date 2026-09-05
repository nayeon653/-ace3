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

### 의료비·요양 인출 라우팅

- 제도상 가능 여부, 자격, 적용 조건, 계좌별 인출 사유와 증빙 조건만 요청하면 Policy만
  호출한다.
- 한도, 세율, 세액, 과세와 세후액만 요청하면 Tax/Payout만 호출한다.
- 가능 여부와 한도·세금·세후액을 함께 요청하면 Policy와 Tax/Payout을 각각 한 번
  호출한다. 의료비·요양이라는 단어 자체는 복수 Domain 호출 조건이 아니다.
- Main은 DC의 제도상 요양 조건과 세법상 의료 목적 요양 조건을 하나로 합치거나 직접
  판정하지 않는다. 세액·한도·세후액도 계산하지 않고 각 Domain Agent의 결과를 통합한다.
- 한 Domain의 결과가 `conditional` 또는 `undetermined`여도 다른 Domain의 확정된
  결론과 계산을 제거하지 않는다.

### DB·DC 퇴직급여 라우팅

- 제도 유형, 평균임금 제외기간, 계속근로·근속 인정과 DB→DC 전환 가능 여부·자격·절차는 Policy만 사용한다.
- 검증된 입력을 사용한 DB·DC 퇴직급여, DC 최소 사용자 부담금과 DB→DC 전환금액 요청은 Tax/Payout만 사용한다.
- 제도 판단과 금액을 함께 요청하면 Policy와 Tax/Payout을 함께 사용한다. 제도 유형과 산식이 불명확한 퇴직급여 금액 요청은 Policy로 확인하며 Tax/Payout이 DB 또는 DC를 임의 선택하게 하지 않는다.
- 입력이 완비된 DB/DC 금액 비교는 Tax/Payout만 사용하고, 적용 제도 판단까지 요청하면 두 Domain을 사용한다.
- 전환 가능 여부와 전환금액은 독립된 판단이다. 계산 결과가 전환 가능을 의미하지 않으며 Main은 두 결론을 합성하지 않는다.
- 급여액은 현재의 인출 단계 세금 Tool에 필요한 이연퇴직소득세 배분액, 재원과 수령 유형을 충족하지 않는다. 최초 퇴직소득세 계산기가 없으므로 급여+세금 요청은 급여 계산을 보존하고 세금 부분을 추가 입력·별도 계산이 필요한 조건부 결과로 남긴다.
- Main은 기간, 근속연수, 급여, 전환금액과 세금을 직접 계산하지 않는다.

### 임원 퇴직소득 한도 라우팅

- 임원 퇴직소득 한도, 임원 퇴직소득 인정액과 한도초과 근로소득은 소득세법상 한도
  계산이며 Tax/Payout만 사용한다. 위 DB·DC 라우팅의 "제도 유형이 불명확한 퇴직급여
  금액" 규칙과는 별개 판단이므로 적용하지 않는다.
- 임원 해당 여부 자체의 제도적 판정은 Policy가 현재 지원하지 않으므로 Main이 Policy와
  Tax/Payout의 허위 복합 판단을 만들지 않는다.
- 한도초과 근로소득은 소득 구분 금액이며 세액이 아니다. 근로소득세까지 요청해도 Main은
  존재하지 않는 세금 계산 Tool이 있는 것처럼 라우팅하지 않는다.

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

복합 질문에서도 각 결과의 `calculations`, 계산별 `input_sources`, `evidence`, `warnings`를
그대로 보존한다. Main에 전달되는 축약 결과나 한 Domain의 상태가 다른 Domain의 전체
결과를 덮어쓰지 않는다.

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

### 프롬프트 인젝션 방어

`PromptInjectionMiddleware(block_user_input=True)`를 Main의 가장 바깥쪽 모델 호출
미들웨어로 적용한다. 원문 `question`과 Human 메시지에서 알려진 한국어·영어 지침 무시,
내부 프롬프트 추출, 역할 사칭 표식을 발견하면 모델·Domain Tool 호출 전에 고정된
자연어 거절 응답을 반환한다. NFKC, 공백, 비표시 서식 문자 정규화는 검사 복사본에만
적용한다. 원문 질문은 변경하지 않으며, `GET /answer`는 기존 5개 필드와 HTTP 200을
유지한다. 이 경우 검색 근거와 Domain 실행 결과는 비어 있다.

Main, Policy, Tax/Payout, Product의 모든 모델 호출에는 패키지 리소스
`pension_agent/prompts/security/input-trust-boundary.md`를 같은 System 메시지에 추가한다.
Tool 응답은 모델 요청 복사본에서만 `{"untrusted_tool_output": 원래 content}`로 감싼다.
모델에는 원래 JSON 결과가 문자열로 포함되며, 그 안의 상태·근거·계산을 데이터로 읽는다.
Tool 호출 ID, 메시지 메타데이터, 원본 state, 근거 본문·UUID와 계산 출처는 보존한다.
정책은 매 호출에 적용되며 그래프 상태에 누적되지 않는다. `create_agent`를 우회하는
카탈로그 planner와 matcher의 직접 HCX 호출에도 같은 System 정책을 적용한다.

추가 분류 모델, 외부 서비스, 설정 옵션은 없다. 기존 HCX-007, 문서 권한, 계산 검증,
도구 호출 상한과 실행 예산을 그대로 사용한다. 정상 연금 질문의 제외 조건·업무 지침
문의와 일부 부정·설명형 문장은 회귀 테스트로 확인한다.

정규식은 알려진 표현을 차단하는 보조 방어다. 공격을 그대로 인용한 질문도 차단될 수
있으며, 우회 표현·인코딩·다국어 공격을 모두 탐지하지는 못한다. Tool 결과 경계와 System
정책은 간접 인젝션에 대한 모델 지침이며 결정론적 차단이나 완전한 방어를 보장하지 않는다.
Domain의 문자열이 응답 조립이나 `think_trace`로 전달되는 경로의 출력 정제도 범위 밖이다.
오프라인 테스트는 차단 로직·배선·원문 보존을 검증하며 실제 HCX의 공격 성공률이나 정상
답변 품질은 별도의 라이브 평가가 필요하다.

설계 참고: [OWASP 프롬프트 인젝션 방어 지침](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html),
[LangChain 모델 호출 미들웨어](https://docs.langchain.com/oss/python/langchain/middleware/custom).

### 호출 제한

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
- `tests/unit/agent/test_prompt_injection.py`
- `tests/unit/agent/test_prompt_injection_integration.py`
- `tests/test_agent_graph_document.py`
