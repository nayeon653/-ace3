---
status: accepted
date: 2026-08-14
type: operations
related:
  - 20260813-main-supervisor-domain-agent-tools.md
  - 20260813-hcx-005-model-factory.md
supersedes:
  - 20260813-13-langsmith-tracing-policy.md
superseded-by: []
---

# 개인 LangSmith 무료 계정의 기본 tracing으로 모든 개발 실행 추적

## 배경

이전 결정은 합성 데이터 전용 smoke만 추적하도록 제한했다. 이 방식은 연결 여부는 확인할
수 있지만 개발자가 실제로 던지는 질문에서 Tool 선택, 복수 도메인 routing, 최종 답변,
지연시간과 token 사용량을 분석하기 어렵다.

현재 시스템에는 고객 계정, 개인정보나 실제 금융정보가 들어오는 기능이 없으므로 개발
질문을 별도로 분류하거나 커스텀 masking 계층을 둘 필요가 없다. LangChain은 LangSmith
환경변수만으로 Agent와 하위 모델·Tool 실행을 자동 추적하므로 별도 client와 tracing
context를 유지하는 것도 현재 범위에 비해 복잡하다.

LangSmith의 개인 Developer plan은 1인 사용과 무료 trace 할당량을 제공하지만 팀 협업용
Plus plan은 유료다. 현재는 운영 서비스가 아니라 개발 단계이므로 공용 workspace와
project를 위해 비용을 지불할 필요가 없고 개발자별 trace를 한곳에 모아야 할 요구도 없다.

## 결정

LangChain이 기본 제공하는 LangSmith 연동만 사용한다. 제품 코드에 별도 LangSmith
client, callback, tracing context, 데이터 분류 gate 또는 metadata 가공 계층을 추가하지
않는다.

각 개발자는 다음 항목을 개인적으로 준비한다.

- 개인 LangSmith 무료 계정과 개인 workspace
- 개인 계정에서 발급한 API key
- 다른 개발자와 구분되는 개인 project
- 커밋되지 않는 로컬 `.env`의 `LANGSMITH_*` 설정

유료 Plus plan을 구매하지 않으며 팀 공용 API key, workspace와 project를 만들거나 배포
secret로 공유하지 않는다. 개인 API key를 문서, 메신저, GitHub 또는 다른 팀원에게
전달하지 않는다.

저장소, CI, 대회 평가와 배포 환경의 `LANGSMITH_TRACING` 기본값은 `false`다. 개발자가
자신의 로컬 환경에서 `LANGSMITH_TRACING=true`로 명시하면 질문 출처를 구분하지 않고
현재 프로세스의 모든 LangChain·LangGraph 실행을 sampling rate `1.0`으로 추적한다.

- `GET /answer`로 받은 질문과 Supervisor state
- Main Supervisor의 시스템 프롬프트와 HCX-005 입출력
- Domain Tool 요청·응답과 이후 연결될 evidence·calculation
- 최종 답변, 실행 순서, 지연시간과 token 사용량

활성화와 비활성화는 LangSmith의 표준 환경변수로만 제어한다. 개인 trace의 접근 권한,
보존과 삭제는 해당 계정 소유자가 관리한다.

## 고려한 대안

- 유료 Plus plan과 공용 project를 사용하면 팀원이 같은 trace를 볼 수 있지만 현재 개발
  단계에는 비용 대비 효용이 작아 채택하지 않는다.
- 별도 LangSmith client와 조건부 tracing context를 구현하면 세밀하게 제어할 수 있지만
  현재는 모든 개발 실행을 허용하므로 불필요한 코드와 테스트가 된다.
- 합성 smoke만 추적하는 기존 방식은 실제 질문의 routing 문제를 확인하기 어려워
  대체한다.

## 결과

- tracing 동작은 LangSmith와 LangChain의 표준 기능에 맡겨 제품 코드가 단순해진다.
- 각 개발자는 개인 Developer plan의 무료 할당량 안에서 자신의 질문과 전체 Agent 실행을
  추적할 수 있다.
- 팀원이 다른 사람의 trace를 직접 볼 수 없으므로 공유가 필요한 결론은 민감정보 없는
  화면 설명이나 `docs/experiments.md`의 요약으로 남긴다.
- 개인 Developer plan의 한도나 정책이 개발을 방해할 때만 유료 Plus plan 도입을 다시
  검토한다.
- 고객정보, 개인정보 또는 외부 전송이 제한된 데이터가 들어오는 구조를 추가하기 전에는
  새 ADR로 tracing 범위를 다시 결정한다.

## 관련 자료

- [GitHub 이슈 #17](https://github.com/nayeon653/-ace3/issues/17)
- [대체된 LangSmith 추적 결정](20260813-13-langsmith-tracing-policy.md)
- [LangSmith 추적 운영 절차](../operations/langsmith-tracing.md)
- [LangChain 애플리케이션 tracing](https://docs.langchain.com/langsmith/trace-with-langchain)
- [LangSmith plan과 가격](https://www.langchain.com/pricing)
