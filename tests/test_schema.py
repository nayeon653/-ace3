"""GET /answer 응답 스키마 검증.

서버가 아직 구현되지 않았으므로 skip 처리한다.
server/ 구현 완료 후 TODO를 해소하고 실제 클라이언트 호출로 교체할 것.
"""
import pytest

REQUIRED_KEYS = {
    "question_id",
    "question",
    "retrieved_context",
    "think_trace",
    "answer",
}


@pytest.mark.skip(reason="TODO: server/ 구현 후 실제 GET /answer 호출로 교체")
def test_answer_response_has_required_keys():
    # TODO: FastAPI TestClient로 GET /answer?question_id=...&question=... 호출
    response_json = {}
    assert REQUIRED_KEYS.issubset(response_json.keys())
