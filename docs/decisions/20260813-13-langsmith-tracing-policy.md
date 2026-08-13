---
status: accepted
date: 2026-08-13
type: operations
related:
  - 20260813-main-supervisor-domain-agent-tools.md
  - 20260813-hcx-005-model-factory.md
supersedes: []
superseded-by: []
---

# 합성 데이터 개발 실행에 한해 LangSmith 전체 추적을 허용

## 배경

Main Supervisor는 사용자 질문, Tool 요청과 응답, 도메인 판단, 근거 청크, 계산 기록과
최종 답변을 한 실행 안에서 다룬다. 임시 Domain Runner와 HyperCLOVA X를 처음 연결하는
단계에서는 이 실행 경계를 한 화면에서 확인할 수 있어야 Tool 선택, State 누적과 답변
생성 문제를 빠르게 찾을 수 있다.

LangSmith의 자동 추적은 이 목적에 유용하지만 외부 서비스에 실행 데이터를 전송한다.
실제 질문, 대회 평가 질문과 제공 문서에는 외부 전송 여부를 별도로 검토해야 하는 내용이
포함될 수 있다. 시크릿이나 Provider의 원시 오류도 실행 데이터와 함께 기록되면 안 된다.
또한 평가 API는 LangSmith의 설정이나 장애와 관계없이 계속 동작해야 한다.

현재 실연결 범위는 실제 검색과 도메인 Agent를 붙이기 전의 합성 데이터 실행이다. 이
구간에서는 일부 필드만 남기는 것보다 실행 입력과 출력을 모두 보는 편이 초기 오류를
찾는 데 유리하다. 따라서 개발 편의와 실제 데이터 보호를 실행 단계로 나누어 결정한다.

## 결정

### 합성 데이터 개발 구간

팀이 통제하는 개발 환경에서 합성 데이터만 사용하는 실행은 LangSmith 전체 추적을
허용한다. 전체 추적에는 다음 내용이 포함될 수 있다.

- Main Supervisor의 합성 질문과 메시지, 시스템 프롬프트, 모델 입력과 출력
- 합성 `DomainRequest`, `DomainResult`, `DomainToolResult`와 Tool 입출력
- 합성 `EvidenceChunk`, `CalculationResult`, 판단, 경고와 정제된 오류
- 실행 트리, run 이름, tag, 허용된 metadata, 상태와 지연시간

이 구간의 sampling rate는 `1.0`으로 두어 모든 실행을 추적한다. 저장소와 CI의 기본값은
비활성화로 유지하고, 개발자가 로컬 또는 격리된 개발 실행에서 명시적으로 활성화한다.
trace는 합성 데이터 전용 LangSmith project로 분리한다.

여기서 합성 데이터는 실제 질문, 평가 질문, 제공 문서, 개인정보와 실제 금융정보를
복사·요약·변형하지 않고 테스트 목적으로 새로 만든 데이터다. 실제 자료의 일부를 이름만
바꾸거나 문장을 고쳐 사용한 경우는 합성 데이터로 보지 않는다.

### 항상 전송하지 않는 데이터

전체 추적이 활성화되어도 다음 데이터는 LangSmith로 전송하지 않는다.

- API key, access token, 인증 header, cookie와 `.env` 값
- Provider의 원시 예외 객체와 예외 연결, stack trace
- 로컬 절대 경로, 사용자명, hostname과 내부 endpoint
- 실제 개인정보, 계좌·고객 식별정보와 그 밖의 실제 금융정보

오류는 애플리케이션에서 정제한 고정 메시지나 오류 코드만 추적한다. 시크릿은 합성 데이터가
아니므로 어떤 환경에서도 전체 추적의 범위에 포함되지 않는다.

### 실제 데이터 진입 이후

다음 중 하나라도 실행 경로에 들어오기 전 LangSmith tracing을 비활성화한다.

- 실제 사용자 질문 또는 대회 평가 질문
- 제공 문서 원문, 파싱 결과, 검색 청크 또는 그 내용을 요약·변형한 데이터
- 실제 사용자 조건을 사용한 계산 입력과 결과
- 외부 요청을 받는 평가·운영 API

개발 환경이라도 실제 데이터가 포함되면 같은 규칙을 적용한다. masking이나 sampling만으로
실제 데이터 추적을 허용하지 않는다. 이후 실제 데이터의 제한적 추적이 필요하면 전송 필드,
승인 주체, 보존 기간과 삭제 절차를 정한 새 결정 기록을 먼저 채택한다.

환경별 기본 정책은 다음과 같다.

| 환경 | 기본값 | 활성화 조건 | 추적 범위 |
|---|---|---|---|
| 로컬·CI | 비활성화 | 없음 | 전송하지 않음 |
| 개발 | 비활성화 | 명시적 opt-in과 합성 데이터 전용 실행 | 합성 실행 데이터 100% |
| 대회 평가 | 비활성화 고정 | 활성화하지 않음 | 전송하지 않음 |
| 운영 | 비활성화 고정 | 새 결정 전에는 활성화하지 않음 | 전송하지 않음 |

### 보존과 장애 격리

합성 trace는 LangSmith에서 제공하는 가장 짧은 보존 등급을 사용하고 extended retention이나
dataset으로 승격하지 않는다. 실연결 검증이 끝나면 trace 또는 합성 데이터 전용 project를
삭제한다. 삭제 전에도 실제 데이터 실행으로 전환하지 않는다.

LangSmith는 선택적 개발 관측 도구다. API key 누락, 설정 오류, timeout, 전송 실패와
LangSmith 장애는 Main Supervisor, Answer Service, `GET /answer`와 `/health`를 실패시키거나
응답을 변경해서는 안 된다. 이 원칙을 지킬 수 없는 실행에서는 tracing을 비활성화한다.

구체적인 활성화, 비활성화, 데이터 판정, 삭제와 사고 대응 절차는
[`docs/operations/langsmith-tracing.md`](../operations/langsmith-tracing.md)를 따른다.

## 고려한 대안

- LangSmith를 전혀 사용하지 않고 로컬 로그만 남기면 외부 전송 위험은 가장 작지만
  Supervisor와 Tool의 중첩 실행을 실연결 단계에서 확인하기 어렵다.
- 처음부터 metadata allowlist만 추적하면 실제 데이터 연결 이후 확장하기 쉽지만 합성
  Runner 단계의 모델·Tool 입출력 문제를 진단하는 정보가 부족하다.
- masking한 실제 데이터를 LangSmith로 보내면 운영 관측 범위는 넓지만 누락된 규칙이나
  새 필드로 원문이 전송될 위험이 있어 채택하지 않았다.
- Self-hosted LangSmith는 데이터 통제를 강화할 수 있지만 현재 팀 규모와 제출 일정에 비해
  배포·보안·백업·삭제 운영 부담이 크다.
- sampling은 trace 양과 비용을 줄일 뿐 특정 민감 실행의 전송을 확실히 막지 못하므로
  실제 데이터 보호 수단으로 채택하지 않았다.

## 결과

- 후속 이슈 #17은 합성 데이터 전용 개발 project에서 100% 전체 추적으로 진행할 수 있다.
- 저장소 기본값과 일반 CI는 LangSmith 계정이나 API key 없이 동작한다.
- 실제 검색, 제공 문서, 평가 질문이나 외부 API를 연결하는 작업은 실행 전에 tracing이
  꺼져 있는지 확인해야 한다.
- LangSmith에서 얻은 trace는 개발 진단용 임시 데이터이며 제품의 근거나 평가 기록으로
  사용하지 않는다.
- 실제 데이터 관측이 필요해지면 이 결정을 직접 수정하지 않고 후속 ADR로 대체한다.

## 관련 자료

- [GitHub 이슈 #13](https://github.com/nayeon653/-ace3/issues/13)
- [후속 LangSmith 연동 이슈 #17](https://github.com/nayeon653/-ace3/issues/17)
- [LangSmith 민감정보 추적 방지](https://docs.langchain.com/langsmith/mask-inputs-outputs)
- [LangSmith 조건부 추적](https://docs.langchain.com/langsmith/conditional-tracing)
- [LangSmith trace sampling](https://docs.langchain.com/langsmith/sample-traces)
- [LangSmith data retention](https://docs.langchain.com/langsmith/administration-overview#data-retention)
- [Main Supervisor와 도메인 Agent Tool 구조](20260813-main-supervisor-domain-agent-tools.md)
