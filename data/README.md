# 로컬 데이터 디렉토리

이 디렉터리의 원본과 생성 산출물은 Git에 커밋하지 않습니다. 필요한 하위
디렉터리는 파이프라인 실행 시 생성합니다.

```text
data/
├── raw/<collection>/                 # 주최측 원본, 수정 금지
├── processed/docling/<collection>/   # Docling artifact bundle
├── ocr/                              # 진단용 OCR 중간물 예약 경로
└── indexes/                          # 검색 인덱스
```

- `raw/`의 파일은 제공 문서 원본이자 답변의 최종 근거이므로 수정하거나 덮어쓰지
  않습니다.
- `processed/docling/`의 문서별 디렉터리는 `document.docling.json`, `document.md`,
  `document.html`, `manifest.json`, `assets/`를 한 bundle로 보존합니다. 일부만
  이동하거나 직접
  편집하지 않습니다.
- `ocr/`은 현재 Docling 파서의 기준 결과 저장소가 아닙니다.
- `indexes/`는 파싱 검수 후 retrieval 단계에서 생성합니다.

운영 배포에 검색 인덱스가 필요하면 별도 artifact 저장소에서 주입하고 Docker 빌드
컨텍스트 전체를 복사하지 않습니다. 전체 실행·저장·검수 규칙은
[`../docs/operations/document-parsing.md`](../docs/operations/document-parsing.md)를
따릅니다.
