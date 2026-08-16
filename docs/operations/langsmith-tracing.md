# LangSmith 추적 운영

이 문서는 개발자가 개인 LangSmith 무료 계정으로 Agent 실행을 추적하는 방법과
활성화·비활성화 기준을 정의한다. 현재 결정은
[`개인 LangSmith 무료 계정의 기본 tracing으로 모든 개발 실행 추적`](../decisions/20260814-langsmith-full-tracing-policy.md)을
따른다.

## 운영 원칙

- LangSmith는 로컬 개발 관측 도구로만 사용한다.
- 유료 Plus plan, 팀 공용 workspace·API key·project를 만들거나 구매하지 않는다.
- 각 개발자가 개인 무료 계정에서 key와 project를 만들고 자신의 로컬 `.env`에 등록한다.
- 저장소, CI, 대회 평가와 배포 환경에서는 tracing을 비활성화하고 LangSmith key를
  주입하지 않는다.
- 개인 로컬 환경에서 tracing을 켜면 질문 출처를 구분하지 않고 모든 Agent 실행을
  추적한다.
- 고객정보나 개인정보가 들어오는 구조를 추가하기 전에는 이 정책을 다시 검토한다.

## 개인 계정 준비

각 개발자가 자신의 LangSmith 계정에서 다음을 준비한다.

1. 개인 무료 계정을 만든다.
2. 개인 workspace에서 API key를 발급한다.
3. 다른 개발자와 구분되는 개인 project 이름을 정한다.
4. 발급한 값은 저장소에 커밋되지 않는 자신의 `.env`에만 입력한다.

개인 project 이름은 `pension-agent-dev-<github-id>`처럼 구분 가능하게 정한다. 다른
개발자의 workspace에 초대하거나 API key를 전달하지 않는다. 무료 plan의 사용량과 trace
보존은 각 계정 소유자가 관리한다.

## 환경변수

LangChain과 LangSmith가 기본 지원하는 환경변수만 사용한다.

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<개인 API key>
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_WORKSPACE_ID=<개인 workspace ID>
LANGSMITH_PROJECT=pension-agent-dev-<github-id>
LANGSMITH_TRACING_SAMPLING_RATE=1.0
```

`LANGSMITH_WORKSPACE_ID`는 API key가 하나의 workspace에만 연결되어 있으면 생략할 수 있다.
미국 외 region의 계정은 해당 region의 endpoint를 사용한다. endpoint에는 trailing slash를
붙이지 않는다.

`LANGSMITH_API_KEY`와 workspace ID는 개인 설정이다. GitHub Actions secret, 팀 공용
secret manager, 배포 환경변수나 공유 문서에 등록하지 않는다.

## 활성화와 추적 범위

로컬 `.env`에서 `LANGSMITH_TRACING=true`로 설정하고 API 서버를 재시작한다.

```bash
uv run uvicorn pension_agent.api.app:app --env-file .env
```

`.env` 파일을 만드는 것만으로 해당 값이 서버 프로세스 환경에 자동 등록되지는 않는다.
`--env-file .env`는 Uvicorn이 애플리케이션을 import하기 전에 `LANGSMITH_*`를 포함한
로컬 설정을 프로세스 환경변수로 주입한다. LangSmith 기본 tracing은 이 프로세스
환경변수를 읽어 활성화 여부, endpoint, workspace와 project를 결정한다.

서버가 실행되면 원하는 질문을 직접 호출한다.

```bash
curl --get http://127.0.0.1:8000/answer \
  --data-urlencode 'question_id=TRACE-001' \
  --data-urlencode 'question=연금계좌를 이전하고 상품도 바꾸려면 무엇을 확인해야 하나요?'
```

별도 tracing 코드는 필요하지 않다. LangChain·LangGraph의 기본 연동이 다음 실행을 같은
trace tree에 기록한다.

- Main Supervisor 입력 state와 시스템 프롬프트
- HCX-005 모델 입력·출력
- 선택된 Domain Tool의 요청·응답
- 최종 모델 호출과 답변
- 실행 순서, 지연시간과 제공되는 token 사용량

현재 구조에서는 고객정보나 개인정보가 들어오지 않으므로 고정 smoke와 개발자가 직접
작성한 질문을 구분하지 않는다. tracing이 켜진 로컬 프로세스의 모든 Agent 실행이 같은
개인 project에 기록된다.

## 확인

개인 LangSmith project에서 다음을 확인한다.

1. Main Supervisor 아래에 모델과 선택된 `analyze_*` Tool 실행이 연결되는지 확인한다.
2. 단일·복수 도메인 질문에서 Tool 선택이 의도와 일치하는지 확인한다.
3. Tool 결과가 최종 답변에 반영되는지 확인한다.
4. 질문별 지연시간과 token 정보가 제공되는지 확인한다.

팀에 공유할 필요가 있는 결론은 API key, 질문 원문이나 trace 링크를 공유하지 않고
`docs/experiments.md`에 재현 방법과 관찰 결과만 요약한다.

## 비활성화

평소 기본값은 다음과 같다.

```dotenv
LANGSMITH_TRACING=false
```

값을 바꾼 뒤 실행 중인 서버를 재시작한다. CI와 배포 환경에는 `LANGSMITH_API_KEY`를
등록하지 않고 `LANGSMITH_TRACING=false`를 유지한다.

## 비용과 plan 변경

현재 공식 가격 정책상 개인 Developer plan은 1인 사용과 무료 trace 할당량을 제공한다.
현재는 개발 단계이며 공용 운영 관측이 필요하지 않으므로 팀 협업용 Plus plan 비용을
지불하지 않는다. 다음 조건 중 하나가 생길 때만 Plus plan 또는 다른 관측 방식을 검토한다.

- 여러 팀원이 같은 trace를 동시에 봐야 하는 운영 요구
- 개인 무료 plan의 사용량·보존 한도가 반복적으로 개발을 방해하는 경우
- 공용 dashboard, 권한 관리나 장기 보존이 필요한 경우

구체적인 할당량과 가격은 변경될 수 있으므로 가입 시
[LangSmith 공식 가격](https://www.langchain.com/pricing)을 확인한다.

## 장애와 데이터 구조 변경

LangSmith 오류가 의심되면 먼저 `LANGSMITH_TRACING=false`로 바꾸고 서버를 재시작해 제품
실행과 분리한다. 개인 project의 불필요한 trace와 API key 폐기는 계정 소유자가 직접
처리한다.

고객 계정, 개인정보, 실제 고객 금융정보 또는 외부 전송이 제한된 데이터를 입력받는
구조를 추가하기 전에는 새 ADR에서 tracing 범위, 접근 권한, 보존과 masking 정책을 다시
결정한다.
