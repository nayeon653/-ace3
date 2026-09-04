---
status: accepted
date: 2026-09-05
type: architecture
related:
  - 20260813-main-supervisor-domain-agent-tools.md
  - 20260820-80-router-search-service.md
supersedes:
  - 20260824-96-selective-hcx-007-models.md
superseded-by: []
---

# 모든 생성 LLM 역할을 HCX-007 비추론 모드로 통일

## 배경

기존 결정은 위임과 상품 검색 판단의 영향이 큰 Main Supervisor와 Product Agent
ReAct에 HCX-007을 사용하고 Policy·Tax/Payout Agent와 Product Catalog Planner에는
HCX-005를 사용했다. 단순한 역할에는 상위 모델의 비용 대비 이득이 작을 수
있다는 판단이었다.

Policy Agent의 제도 비교 질문을 점검하면서 검색 계층이 질문에 직접 답하는 청크를
반환했는데도 Agent가 요청된 비교 항목을 누락하거나 적용 조건이 다른 청크까지
근거로 선택하는 사례가 확인됐다. 이는 검색 결과 이후의 Tool 호출, 근거 선별과
지시 이행 성능이 도메인 답변 품질에 직접 영향을 준다는 것을 보여준다.

결정 시점의 CLOVA Studio 공식 요금은 HCX-005와 HCX-007의 입력·출력 토큰
단가가 같다. 단, 모델이 생성하는 토큰 수와 호출 횟수가 달라지면 실제 요청별
비용과 지연은 달라질 수 있다.

## 결정

모든 생성 LLM 역할에 `HCX-007`을 사용하고 Thinking은 `none`으로 고정한다.

| 역할 | 모델 | Thinking |
|---|---|---|
| Main Supervisor | `HCX-007` | `none` |
| Policy Agent | `HCX-007` | `none` |
| Tax/Payout Agent | `HCX-007` | `none` |
| Product Agent ReAct | `HCX-007` | `none` |
| Product Catalog Planner | `HCX-007` | `none` |

모델 버전은 통일하지만 역할별 `ChatClovaXConfig`와 모델 인스턴스 경계는 유지한다.
후속 품질 검증에서 특정 역할의 생성 설정을 별도로 조정하거나 부분 롤백할 수
있게 하기 위해서다. 모든 인스턴스는 기존처럼 런타임 소유 HTTP client와 프로세스 단위
HCX 동시성 제한을 공유한다. 모델명과 생성 설정은 환경변수로 덮어쓰지 않는다.

Product Catalog Planner를 포함한 생성 경로는 Function Calling을 사용하므로
HCX-007의 Thinking을 비활성화한다. 검색 쿼리와 문서를 벡터로 변환하는 CLOVA
`bge-m3`는 임베딩 전용 모델이며 생성 LLM 통일 범위에 포함하지 않는다.

## 고려한 대안

- Main Supervisor와 Product ReAct만 HCX-007을 사용하는 기존 구성은 변경 범위가 작지만
  도메인 Agent의 근거 선별·지시 이행 품질을 같은 모델 기준으로 맞추지 못하므로
  대체한다.
- HCX-005 실패 시에만 HCX-007로 재시도하면 평균 사용량을 줄일 수 있지만, 실패
  판정과 중복 호출이 새 실행 분기를 만든다. 두 모델의 현재 토큰 단가도 같으므로
  채택하지 않는다.
- 통합 config와 단일 모델 인스턴스를 모든 역할이 공유하면 조립 코드가 줄지만,
  역할별 검증·조정·롤백 경계도 함께 사라진다. 이번 변경은 모델 버전 통일에만
  제한한다.
- Thinking을 활성화하면 복잡한 판단을 보조할 수 있지만 Function Calling 경로와
  호환되지 않고 지연과 사용량을 늘릴 수 있어 채택하지 않는다.

## 결과

- Main·Domain·Catalog Planner가 같은 세대의 지시 이행과 Function Calling 동작을
  사용한다.
- 결정 시점의 공식 토큰 단가 기준으로는 모델 버전 변경 자체의 단가 증가가
  없다. 실제 비용은 호출 횟수와 입·출력 토큰 수로 계속 확인한다.
- 모델 변경은 검색 라우팅, 청크, 임베딩이나 프롬프트 문제를 자동으로 해결하지
  않는다. 후속 평가에서 각 계층의 원인을 계속 분리한다.
- 실제 `/answer` 호출에서 Product Catalog Planner의 운용사별 목록 조회와 Tax/Payout의
  근거 기반 세금 설명은 정상 동작했다.
- 사용자 입력값으로 연금수령한도를 산출하는 경로에서 HCX-007은 검색과 Calculation
  Tool까지 호출했지만, 질문 원문을 인용한 `source`에서 조사 한 글자를 생략해 exact-match
  검증을 통과하지 못했다. 같은 질문의 HCX-005 비교 호출은 검색 선행 순서를 끝까지 따르지
  못했으므로 모델 통일로 새로 생긴 회귀로 보지는 않지만, Tax/Payout 프롬프트와 계산 입력
  출처 계약의 별도 개선이 필요하다.

## 관련 자료

- [PR #151](https://github.com/nayeon653/-ace3/pull/151)
- [CLOVA Studio 모델](https://guide.ncloud-docs.com/docs/clovastudio-model)
- [CLOVA Studio 요금](https://www.ncloud.com/product/aiService/clovaStudio#pricing)
- [HCX-007 Function Calling 문제 해결](https://guide.ncloud-docs.com/docs/clovastudio-troubleshoot-generation)
