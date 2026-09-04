---
status: superseded
date: 2026-08-24
type: architecture
related:
  - 20260813-main-supervisor-domain-agent-tools.md
  - 20260820-80-router-search-service.md
supersedes:
  - 20260813-hcx-005-model-factory.md
superseded-by:
  - 20260905-all-generation-hcx-007.md
---

# Main Supervisor와 Product ReAct에 HCX-007을 선택 적용

## 배경

초기 런타임은 하나의 HCX-005 인스턴스를 Main Supervisor, 모든 Domain Agent와 Product
Catalog Planner에 주입했다. 실제 상품 카탈로그·상세 검색 실험에서는 Main Supervisor의
위임과 Product Agent의 상품 식별, 검색 순서 및 근거 제출 판단이 전체 결과 품질에 큰
영향을 주었다. 반면 Catalog Planner는 전체 카탈로그를 입력받아 제한된 Query Tool만
호출하므로 상위 모델 적용 시 반복 입력 비용 대비 이득이 상대적으로 작다.

## 결정

역할별 HyperCLOVA X 모델을 다음과 같이 버전 관리한다.

| 역할 | 모델 | Thinking |
|---|---|---|
| Main Supervisor | `HCX-007` | `none` |
| Product Agent ReAct | `HCX-007` | `none` |
| Policy·Tax/Payout Domain Agent | `HCX-005` | 사용하지 않음 |
| Product Catalog Planner | `HCX-005` | 사용하지 않음 |

Main Supervisor와 Product ReAct는 모두 Function Calling을 사용하므로 HCX-007의 Thinking을
비활성화한다. 별도 최종 합성 호출을 추가하지 않으며 Main Supervisor의 Tool 선택과 최종
답변은 같은 HCX-007 비추론 설정을 사용한다.

런타임은 역할별 `ChatClovaX` 인스턴스를 만들되 하나의 런타임 소유 HTTP client와 HCX
동시성 제한을 공유한다. Product Agent Factory는 ReAct 모델과 Catalog Planner 모델을
서로 다른 인자로 받는다. 모델명과 생성 설정은 환경변수로 덮어쓰지 않는다.

## 고려한 대안

- 모든 Agent와 Catalog Planner를 HCX-007로 전환하면 구성이 단순하지만 전체 카탈로그를
  반복 입력하는 Planner까지 상위 단가가 적용되고, 단순 Domain 흐름의 비용 대비 이득을
  확인하지 못했으므로 채택하지 않았다.
- HCX-005 실패 시에만 HCX-007로 재시도하면 평균 비용을 더 줄일 수 있지만 실패 판정과
  중복 호출이 새로운 실행 분기를 만들므로 이번 범위에서 제외했다.
- HCX-007 Thinking을 최종 답변에서만 사용하려면 Tool 호출과 최종 합성 모델 경계를
  분리해야 한다. 현재 API 지연과 호출 수를 늘리므로 후속 실험 대상으로 남겼다.

## 결과

- 위임과 상품 검색 ReAct처럼 판단 가치가 큰 호출에만 HCX-007 비용을 사용한다.
- Catalog Planner와 다른 Domain Agent는 HCX-005를 유지한다.
- 모든 HCX 호출은 기존 프로세스 단위 동시성 상한과 HTTP 연결 수명주기를 공유한다.
- 역할별 정확도, 지연시간과 토큰 비용은 같은 질의셋의 후속 A/B 실험으로 재검토한다.

## 관련 자료

- [GitHub 이슈 #96](https://github.com/nayeon653/-ace3/issues/96)
- [CLOVA Studio 모델](https://guide.ncloud-docs.com/docs/clovastudio-model)
- [HCX-007 Function Calling 문제 해결](https://guide.ncloud-docs.com/docs/clovastudio-troubleshoot-generation)
