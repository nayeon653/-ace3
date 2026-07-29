.PHONY: help setup ingest index eval serve check hooks

help: ## 사용 가능한 타깃 목록 출력
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-10s %s\n", $$1, $$2}'

setup: ## 의존성 설치
	pip install -r requirements.txt

ingest: ## 원본 문서 파싱/OCR/정규화 실행
	python -m ingest.run

index: ## 청킹/임베딩/인덱싱 실행
	python -m index.run

eval: ## 평가셋 실행
	python -m eval.harness.run

serve: ## 로컬 API 서버 기동
	uvicorn server.main:app --reload --port $${PORT:-8000}

check: ## 린트 + 테스트
	ruff check .
	pytest -q

hooks: ## 훅 경로를 .githooks로 설정 (팀원 각자 최초 1회 실행)
	git config core.hooksPath .githooks
	chmod +x .githooks/* 2>/dev/null || true
