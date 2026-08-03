# Docling Parser

`-ace3`의 문서 파싱 단계에서 사용하는 저장소 내부 오프라인 Python 도구입니다.
PDF, DOCX, PPTX, XLSX를 고정 로컬 EasyOCR 또는 NAVER CLOVA General OCR V2
프로필로 파싱해 Markdown, Docling JSON, manifest와 이미지 assets를 생성합니다.

평가 API의 런타임 패키지가 아닙니다. Docling, PyTorch와 NumPy 1.x 의존성이 API
환경에 섞이지 않도록 자체 `pyproject.toml`, `uv.lock`, `.venv`를 사용합니다.
제품 코드에서 이 패키지를 import하지 않고, 오프라인에서 생성한 bundle을 후속
ingest/retrieval 단계가 소비합니다.

실행 명령, 저장 위치, OCR 선택, 외부 전송, 실패 처리와 검수 규칙의 유일한 원본은
[`../../docs/operations/document-parsing.md`](../../docs/operations/document-parsing.md)입니다.
저장소 checkout 전체를 배포 단위로 사용합니다.

## 개발 확인

`uv`가 필요하며 로컬과 CI 모두 `.python-version`에 고정한 Python 3.12를 사용합니다.

```bash
uv sync --locked --project tools/docling_parser
uv run --frozen --project tools/docling_parser python tools/docling_parser/scripts/parse_document.py --help
uv run --frozen --project tools/docling_parser pytest -q --capture=sys tools/docling_parser/tests
```

파싱 결과에 영향을 주는 설정을 바꿀 때 기존 프로필 ID의 의미를 변경하지 않습니다.
새 설정에는 `-v2`처럼 새 프로필 ID와 회귀 테스트를 추가합니다.
