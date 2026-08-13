# LangSmith 추적 운영

이 문서는 LangSmith trace의 활성화, 데이터 범위, 비활성화, 보존·삭제와 사고 대응의
단일 운영 기준이다. 채택 배경과 대안은
[`합성 데이터 개발 실행에 한해 LangSmith 전체 추적을 허용`](../decisions/20260813-13-langsmith-tracing-policy.md)을
참고한다.

## 기본 원칙

- 저장소, CI, 대회 평가와 운영 환경의 tracing 기본값은 비활성화다.
- 팀이 통제하는 개발 환경에서는 합성 데이터 전용 실행에 한해 명시적으로 활성화한다.
- 합성 데이터 실행은 입력과 출력을 숨기지 않고 sampling rate `1.0`으로 모두 추적한다.
- 시크릿은 데이터 종류와 환경에 관계없이 외부 trace에 포함하지 않는다.
- 실제 질문이나 제공 문서가 들어오는 실행은 masking 여부와 관계없이 추적하지 않는다.
- LangSmith 설정이나 장애는 제품 실행과 평가 API에 영향을 주지 않는다.

## 데이터 판정

### 합성 데이터

다음 조건을 모두 만족해야 합성 데이터다.

1. 테스트 목적으로 새로 만든 질문, 문서 청크, 계산 입력과 결과다.
2. 실제 질문, 대회 평가 질문, 제공 문서, 개인정보와 실제 금융정보를 복사하거나
   요약·변형하지 않았다.
3. 특정 실제 사용자나 문서를 다시 식별할 수 있는 값이 없다.
4. 실행에 연결된 모든 Runner, fixture와 검색 결과도 같은 조건을 만족한다.

판단이 불분명하면 실제 데이터로 취급하고 tracing을 비활성화한다.

### 추적 가능한 합성 실행 데이터

합성 데이터 조건을 만족하는 개발 실행에서는 다음 항목을 추적할 수 있다.

| 실행 영역 | 추적 가능한 내용 |
|---|---|
| Supervisor | 합성 `question_id`, 질문, 메시지, 시스템 프롬프트, 최종 답변 |
| Model | 모델 입력과 출력, model name, token·지연시간 정보 |
| Tool | `objective`, Tool 입력·출력, 호출 순서와 상태 |
| Domain | `DomainRequest`, `DomainResult`, `DomainToolResult` 전체 |
| Evidence | 합성 `EvidenceChunk`의 식별자, 위치와 본문 |
| Calculation | 합성 `CalculationResult`의 함수명, 입력, 결과와 단위 |
| Error | 정제된 오류 코드·메시지와 실행 상태 |

### 항상 금지하는 데이터

다음 항목은 합성 실행에서도 추적하지 않는다.

| 분류 | 금지 예시 |
|---|---|
| 인증정보 | LangSmith·CLOVA Studio API key, access token, 인증 header, cookie |
| 환경정보 | `.env` 내용, 사용자명, hostname, 로컬 절대 경로, 내부 endpoint |
| 원시 오류 | Provider 예외 객체, 예외 연결, stack trace, 요청·응답 header |
| 실제 입력 | 실제 사용자 질문, 대회 평가 질문, 개인정보, 실제 금융정보 |
| 제공 자료 | 제공 문서 원문, 파싱 결과, 검색 청크와 이를 요약·변형한 내용 |
| 실제 계산 | 실제 사용자 조건을 사용한 계산 입력과 결과 |

run name, tag와 metadata에는 자유 형식 질문, 문서 내용이나 오류 문자열을 넣지 않는다.
허용 metadata는 다음 allowlist로 제한한다.

- 실행 환경과 애플리케이션 버전
- commit SHA
- `HCX-005` 같은 model name
- `policy`, `tax_payout`, `product` 같은 domain name
- 실행 상태와 지연시간
- `synthetic-full-v1` trace policy version

## 환경별 정책

| 환경 | tracing | sampling | 입력·출력 | 비고 |
|---|---|---:|---|---|
| 로컬 기본값 | 비활성화 | `0` | 전송 안 함 | 저장소 기본값 |
| 합성 데이터 개발 | 명시적 활성화 | `1.0` | 전체 추적 | 전용 project 사용 |
| 일반 CI | 비활성화 | `0` | 전송 안 함 | 계정과 API key 불필요 |
| 대회 평가 | 비활성화 고정 | `0` | 전송 안 함 | 평가 질문 포함 |
| 운영 | 비활성화 고정 | `0` | 전송 안 함 | 새 ADR 전까지 금지 |

내부 품질 평가라도 실제 제공 문서나 평가 질문을 사용하면 이 표의 대회 평가와 같은
정책을 적용한다.

## 활성화 절차

후속 구현에서 정한 정확한 환경변수 이름과 실행 명령을 사용하되, 작업자는 활성화 전에
다음을 확인한다.

1. 실행할 질문, Runner, evidence와 calculation이 모두 합성 데이터인지 확인한다.
2. 실제 `data/raw/` 또는 `data/processed/` 자료를 읽지 않는지 확인한다.
3. 합성 데이터 전용 LangSmith project와 팀 workspace를 선택한다.
4. 개발자 개인의 커밋되지 않는 환경 설정에서만 tracing을 활성화한다.
5. sampling rate가 `1.0`이고 입력·출력 숨김이 비활성화되어 있는지 확인한다.
6. 허용 metadata만 설정하고 시크릿과 내부 환경정보가 payload에 없는지 확인한다.
7. 첫 trace를 확인한 뒤 금지 데이터가 없을 때만 나머지 합성 실행을 계속한다.

shell profile, 공용 개발 이미지나 배포 설정에 tracing 활성값을 영구 저장하지 않는다.
합성 project의 접근 권한은 현재 작업에 필요한 팀원으로 제한한다.

## 비활성화 전환 조건

다음 작업을 시작하기 전에 tracing 활성값을 제거하거나 `false`로 설정하고 전송이 없는지
확인한다.

- 제공 문서 파싱 결과를 retrieval 또는 Agent에 연결한다.
- 실제 질문이나 대회 평가 질문을 실행한다.
- 실제 사용자 조건으로 계산 함수를 호출한다.
- 외부 요청을 받는 `GET /answer`를 실행하거나 배포한다.
- 합성 Runner를 실제 Domain Agent로 교체한다.

전환 확인은 tracing이 꺼진 상태에서 합성 smoke test를 한 번 실행하고 LangSmith에 새
trace가 생성되지 않는지 확인하는 방식으로 수행한다. 이 확인이 끝나기 전에는 실제
데이터를 실행하지 않는다.

## 보존과 삭제

- 합성 project에는 사용 가능한 가장 짧은 보존 등급을 적용한다.
- extended retention, dataset 저장과 공개 공유 링크를 사용하지 않는다.
- #17의 실연결 검증이 끝나면 작업자가 trace 또는 합성 project를 삭제한다.
- 삭제가 끝나지 않았으면 tracing을 끈 상태를 유지하고 실제 데이터 실행과 무관하게
  삭제를 후속 조치한다.
- 보존할 필요가 있는 결론은 원문 trace가 아니라 민감정보가 없는 실험 결과나 ADR로
  요약한다.

## 장애와 사고 대응

LangSmith API key가 없거나 전송이 실패해도 Supervisor와 API 실행을 계속한다. 외부 추적
실패는 정제된 로컬 warning으로만 남기고 사용자 응답, HTTP 상태와 `/health` 결과를
바꾸지 않는다. 반복되는 장애가 있으면 tracing을 비활성화하고 로컬 로그로 진단한다.

금지 데이터가 trace로 전송된 경우 다음 순서로 대응한다.

1. tracing을 즉시 비활성화한다.
2. 노출된 trace 또는 project를 삭제한다.
3. 시크릿이 포함됐다면 해당 key나 token을 폐기하고 재발급한다.
4. 민감한 값을 복사하지 않고 GitHub 이슈에 `urgent` 사고 사실과 조치만 기록한다.
5. 전송 경로와 masking 실패 원인을 수정하고 팀 검토 전에는 tracing을 다시 켜지 않는다.

## 실제 데이터 추적 재검토

실제 데이터의 제한적 추적이 필요하면 구현 전에 새 ADR에서 최소한 다음을 결정한다.

- 필드 단위 allowlist와 masking 실패 시 차단 방식
- 데이터 외부 전송 승인과 LangSmith region·workspace 접근 권한
- 보존 기간, 삭제 담당자와 삭제 검증 방법
- trace가 제품 실행에 영향을 주지 않는 테스트
- 대체 가능한 로컬 구조화 로그와 metrics 범위
