"""공유 환경변수 예시 파일의 회귀 조건을 검증한다."""

from collections import Counter
from pathlib import Path


def test_env_example_does_not_repeat_keys() -> None:
    env_example = Path(__file__).resolve().parents[3] / ".env.example"
    keys = [
        line.partition("=")[0].strip()
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    ]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)

    assert duplicates == []
