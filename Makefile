.PHONY: help setup check build lock hooks qdrant-up qdrant-down qdrant-status qdrant-check qdrant-hybrid-test qdrant-index-validate setup-parser parser-test

UV ?= uv
PARSER_PROJECT ?= tools/docling_parser
QDRANT_COMPOSE ?= docker compose -f infra/compose.yaml

help: ## 사용 가능한 타깃 목록 출력
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-16s %s\n", $$1, $$2}'

setup: ## 런타임 + 개발 의존성 설치
	$(UV) sync --dev

check: ## 린트 + 포맷 + 타입 + 테스트
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy pension_agent
	$(UV) run pytest -q --capture=sys

build: ## wheel과 source distribution 빌드
	$(UV) build

lock: ## 의존성 잠금 파일 갱신
	$(UV) lock

hooks: ## 훅 경로를 .githooks로 설정 (팀원 각자 최초 1회 실행)
	git config core.hooksPath .githooks
	chmod +x .githooks/* 2>/dev/null || true

qdrant-up: ## 로컬 Qdrant 실행
	$(QDRANT_COMPOSE) up --detach qdrant

qdrant-down: ## 로컬 Qdrant 종료 (데이터 볼륨 유지)
	$(QDRANT_COMPOSE) down

qdrant-status: ## 로컬 Qdrant 컨테이너 상태 출력
	$(QDRANT_COMPOSE) ps qdrant

qdrant-check: ## Qdrant readiness와 클라이언트 연결 확인
	$(UV) run --frozen python infra/check_qdrant.py

qdrant-hybrid-test: ## 로컬 Qdrant에서 실제 적재와 기본 Hybrid 검색 검증
	QDRANT_DOCKER_INTEGRATION=1 $(UV) run --frozen pytest -q --capture=sys tests/integration/test_qdrant_docker_hybrid.py

qdrant-index-validate: ## 통합 청크와 source manifest 적재 계약 확인
	$(UV) run --frozen python infra/index_qdrant.py validate

setup-parser: ## 독립 Docling 파서 환경 설치
	$(UV) sync --locked --project $(PARSER_PROJECT)

parser-test: ## Docling 파서 단위 테스트 실행
	$(UV) run --frozen --project $(PARSER_PROJECT) pytest -q --capture=sys $(PARSER_PROJECT)/tests
