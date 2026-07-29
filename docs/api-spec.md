# 평가용 API 명세

주최측이 평가기간(2026-09-07 ~ 09-20) 중 GET으로 호출할 API 명세 골격이다.
엔드포인트 URL은 배포 후 확정한다.

## Endpoint

```
GET {TBD}/answer
```

### 요청 파라미터

| 이름 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `question_id` | string | Y | 질의 고유 ID (주최측 평가셋 기준) |
| `question` | string | Y | 자연어 질의 |

### 응답 (200)

정확히 아래 5개 필드만 포함한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `question_id` | string | 요청받은 `question_id` 그대로 반환 |
| `question` | string | 요청받은 `question` 그대로 반환 |
| `retrieved_context` | array[object] | 실제로 답변에 인용된 근거 문서 목록 (리랭킹/컷오프 후) |
| `think_trace` | string | 조건 분기 판단 과정 요약 |
| `answer` | string | 최종 답변. 확인이 필요한 조건과 조건별 결론을 포함할 수 있음 |

```json
{
  "question_id": "TBD",
  "question": "TBD",
  "retrieved_context": [],
  "think_trace": "TBD",
  "answer": "TBD"
}
```

### 에러 응답

| 상태 코드 | 상황 |
|---|---|
| 400 | 필수 파라미터 누락 |
| 500 | 내부 오류 (근거 검색/생성 실패 등) |

에러 응답도 최소한 `question_id`, `question`은 포함해 반환한다 (TBD —
주최측 요구사항 확인 필요).

## Health Check

```
GET {TBD}/health
```

평가기간 중 서버 생존 여부를 확인하기 위한 엔드포인트. 커밋 SHA를 포함해
현재 배포 버전을 추적할 수 있게 한다.

```json
{
  "status": "ok",
  "commit_sha": "TBD"
}
```
