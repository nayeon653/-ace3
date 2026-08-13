---
status: accepted
date: 2026-08-13
type: architecture
related:
  - 20260813-main-supervisor-domain-agent-tools.md
supersedes: []
superseded-by: []
---

# HCX-005 단일 모델과 ChatClovaX Factory를 채택

## 배경

Main Supervisor는 Domain Agent Tool을 선택한 뒤 그 결과를 최종 자연어 답변으로
통합한다. 두 단계의 모델이 다르면 실행 동작과 장애 원인을 추적하기 어렵고, 모델명과
생성 파라미터를 환경변수로 바꾸게 두면 배포별 동작이 Git 이력 밖에서 달라질 수 있다.

한편 API 키는 저장소에 둘 수 없고 CLOVA Studio 엔드포인트는 실행 환경에 따라 달라질
수 있으므로, 모델 동작 설정과 인증·연결 설정을 분리해야 한다.

## 결정

Main Supervisor의 Tool 선택과 최종 답변 생성에 HCX-005 단일 모델 인스턴스를
사용한다. Pydantic 불변 모델인 `ChatClovaXConfig`는 다음 설정을 보관하고 Git에서
버전 관리한다.

| 설정 | 초기값 |
|---|---:|
| model | `HCX-005` |
| max tokens | `1024` |
| temperature | `0.1` |
| timeout | `30초` |
| retry | `2회` |

HCX-005를 포함한 위 값은 실연결 검증 전에 임의로 정한 초기값이다. 후속 실연결과
품질 실험 결과에 따라 HyperCLOVA X 범위 안에서 config를 변경할 수 있다. 결정이
달라지면 기존 기록을 직접 고치지 않고 후속 결정 기록으로 변경 근거를 남긴다. 배포
환경변수로 모델이나 생성 파라미터를 덮어쓰지는 않는다.

인증·연결 설정은 다음 환경변수만 사용한다.

- `CLOVASTUDIO_API_KEY`: CLOVA Studio API 인증 키
- `CLOVASTUDIO_API_BASE_URL`: OpenAI 호환 API 엔드포인트

`ClovaStudioConnection`은 Pydantic Settings로 위 환경변수와 로컬 `.env` 파일을
선언적으로 읽고, 알 수 없는 값은 모델 설정 오버라이드로 사용하지 않는다. Factory는
불변 모델 config와 인증·연결 설정을 주입받아 `ChatClovaX`를 생성하고, 그 인스턴스를
기존 Main Supervisor 조립 함수에 주입한다. API 키가 없거나 Provider 초기화가
실패하면 원래 예외와 시크릿을 노출하지 않는 애플리케이션 오류로 변환한다.

## 고려한 대안

- Tool 선택은 HCX-005, 최종 답변은 HCX-DASH-002로 분리하면 단계별 최적화는
  가능하지만 현재 검증 범위에서 모델별 차이까지 장애 변수로 추가되므로 채택하지
  않았다.
- 모델명과 생성 파라미터를 환경변수로 두면 배포 중 변경은 쉽지만 검토되지 않은
  설정 차이가 생기므로 채택하지 않았다.
- `ChatClovaX`가 환경변수를 직접 읽게 두면 코드가 짧지만 인증 누락과 오류 정제 경계를
  단위 테스트하기 어려우므로 명시적인 설정 주입 Factory를 선택했다.

## 결과

- Main Supervisor의 모델 동작 설정을 코드 리뷰와 Git 이력에서 확인할 수 있다.
- Function Calling 요청의 생성 토큰 수가 항상 1024 이상임을 config 검증으로 강제한다.
- 인증 키 없이도 설정 검증과 Factory의 누락·초기화 실패 경로를 단위 테스트할 수 있다.
- 실제 CLOVA Studio 네트워크 호출과 초기값 조정은 후속 실연결 이슈에서 검증한다.

## 관련 자료

- [GitHub 이슈 #12](https://github.com/nayeon653/-ace3/issues/12)
- [Main Supervisor와 도메인 Agent Tool 구조](20260813-main-supervisor-domain-agent-tools.md)
