# 로컬 Qdrant 실행과 확인

Docker Compose로 단일 노드 Qdrant를 로컬에서 실행하고 연결을 확인하는 방법을 정리한다.
이 구성은 개발과 적재 실험 전용이며 인증·TLS·백업·고가용성을 제공하는 운영 배포
구성이 아니다.

## 사전 준비

Docker Engine과 Docker Compose v2가 실행 가능한지 확인한다. `qdrant-check`는 프로젝트의
Python 의존성을 사용하므로 저장소 루트에서 최초 한 번 개발 환경도 설치한다.

```bash
docker version
docker compose version
make setup
```

## 구성

[`infra/compose.yaml`](../../infra/compose.yaml)은 다음 로컬 개발 구성을 정의한다.

- Qdrant 이미지: `qdrant/qdrant:v1.19.0`
- HTTP·대시보드: `127.0.0.1:6333`
- gRPC: `127.0.0.1:6334`
- 데이터: `/qdrant/storage`를 Compose named volume에 저장
- 익명 사용 통계: `QDRANT__TELEMETRY_DISABLED=true`로 외부 전송 비활성화

두 포트는 loopback에만 바인딩하므로 같은 컴퓨터에서만 접근할 수 있다. Qdrant peer
통신용 6335는 단일 노드 로컬 구성에서 노출하지 않는다. 이 구성에는 API key와 TLS가
없으므로 port binding을 `0.0.0.0`이나 외부 인터페이스로 확대하지 않는다.

## 실행과 확인

저장소 루트에서 Qdrant를 실행한다. 최초 실행에서는 고정된 이미지를 내려받으므로 시간이
걸릴 수 있다.

```bash
make qdrant-up
make qdrant-status
make qdrant-check
```

`make qdrant-check`는 최대 30초 동안 `/readyz`를 확인한 다음 설치된 `QdrantClient`로
컬렉션 목록을 조회한다. 두 단계가 모두 성공하면 연결 주소와 컬렉션 수를 출력한다.
공식 Qdrant 이미지 내부에 `curl`이 있다고 가정하지 않으며 readiness 검사는 호스트의
Python 환경에서 실행한다.

대시보드는 <http://127.0.0.1:6333/dashboard>에서 확인한다. 호스트에서 실행하는 Python
코드는 다음 주소를 사용한다.

```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://127.0.0.1:6333")
```

이 주소는 호스트 실행 전용이다. 후속 이슈에서 FastAPI를 같은 Compose network에
연결하면 컨테이너 내부에서는 `http://qdrant:6333`을 사용해야 한다.

## 종료와 데이터 초기화

일반 종료는 컨테이너와 network만 제거하고 named volume은 유지한다.

```bash
make qdrant-down
```

다시 `make qdrant-up`을 실행하면 기존 데이터를 그대로 사용한다. 로컬 데이터를 완전히
초기화해야 할 때만 다음 명령을 사용한다.

```bash
docker compose -f infra/compose.yaml down --volumes
```

`--volumes`는 로컬 Qdrant 데이터를 복구할 수 없게 삭제한다. 필요한 collection이 없는지
확인한 뒤 실행한다.

## 문제 해결

| 증상 | 확인할 내용 |
|---|---|
| 6333 또는 6334 포트를 사용할 수 없음 | 해당 포트를 사용 중인 다른 프로세스나 컨테이너를 확인한다. |
| `make qdrant-check`가 30초 후 실패 | `docker compose -f infra/compose.yaml logs qdrant`로 시작 로그를 확인한다. |
| 대시보드에 접근할 수 없음 | `make qdrant-status`로 컨테이너 상태와 port binding을 확인한다. |
| 재실행 후 데이터가 없음 | `down --volumes` 실행 여부와 `ace3-local_qdrant_storage` volume 존재 여부를 확인한다. |
