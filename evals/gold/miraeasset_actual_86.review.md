# PR #130 미래에셋 실제 FAQ 86문항 Gold Answer 구축 보고서

작성일: 2026-08-30
대상 브랜치: `chore/miraeasset-qa-markdown`

## 결론

86개 질문 모두에 대해 제공 문서 스냅샷 기반 목표 답변을 작성했다. FAQ의 `source_answer`는 검색 힌트로만 사용했고, 제공 문서가 질문 전체를 뒷받침하지 못하면 `partial`, `unsupported`, `temporal_gap`으로 명시했다.

| 구분 | 건수 |
|---|---:|
| `supported` | 29 |
| `partial` | 36 |
| `unsupported` | 21 |
| `temporal_gap` | 0 |
| 합계 | 86 |

정답셋에는 필수 주장 142개, 고유 Docling 근거 223개, 문항별 근거 참조 260개가 있다. 원본·bundle·parser·Drive provenance를 고정한 출처는 28개이고, 정확한 인용문이 그대로 포함된 retrieval chunk 연결은 180개다.

여기서 `supported`는 법률·세무 사실의 영구적 진실이 아니라, 고정된 제공 문서 스냅샷이 답변의 필수 주장을 직접 뒷받침한다는 뜻이다.

## 산출물

- [Gold Answer JSONL](miraeasset_actual_86.jsonl): 질문, 보수적 정답, 필수 주장, 근거 ID, 공백, 금지 주장
- [Markdown 정답표](miraeasset_actual_86.table.md): 86문항의 목표 답변과 정확한 Docling 근거 위치
- [Docling 근거 레지스트리](miraeasset_actual_86.evidence.json): item_ref, page/slide, bbox, charspan, table cell, 인용문, retrieval chunk
- [출처 레지스트리](miraeasset_actual_86.sources.json): 원본 SHA-256, Drive URL, variant별 bundle ID, parser profile/digest, Docling JSON SHA-256
- [Gold manifest](miraeasset_actual_86.manifest.json): 질문·정답·출처·근거·코퍼스 스냅샷과 해시
- [Gold validator](../harness/validate_miraeasset_gold.py): CI 구조 검증과 로컬 원문 전체 검증

## 원문과 코퍼스 고정

| 대상 | 고정값 |
|---|---|
| Google Drive 전달 폴더 | `1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV` |
| 문서 메타데이터 Sheet | `1MVeNerq-UieyknUSwXCbSndPCYxwP8PUbyL9CjUrsHw` |
| Docling archive | `docling_bundles_20260826.tar.gz` |
| Archive SHA-256 | `b182df76e1ae77ab6ec397f4888121087dedbea069be27b31d4713c3b5dab10b` |
| Archive 크기 | 244,345,240 bytes |
| 전달 bundle | 158개, 모두 `status=success` |
| Retrieval collection | `pension_documents_v1`, 19,747 points |
| Retrieval manifest SHA-256 | `62d3d9e4d9b7d7fc8fd800264f059e8b5617eab72284f3a345723cf87f3fc5c0` |
| Retrieval chunks SHA-256 | `10742e98de05871d48619cef6c912bfc50eba0d844a50a6e77be0c26f67bd395` |

## Parser drift와 원본 PDF 시각 대조

최종 전달물의 `docling-no-ocr-formula-v1`이 이미지형 PDF 본문을 유실한 경우에만, 동일 SHA-256 원본에서 생성된 기존 OCR bundle을 `review_local_ocr` 근거로 함께 고정했다. 아래 페이지는 원본 PDF를 2배율로 렌더링해 사람이 직접 대조했으며, OCR 오탈자는 답변에서 원본 표기를 따랐다.

| 원본 | delivery profile | review profile | 시각 대조 페이지 |
|---|---|---|---|
| `doc24.pdf` | `docling-no-ocr-formula-v1` | `docling-local-ocr-v1` | 3, 4, 5, 6, 15, 16 |
| `doc3.pdf` | `docling-no-ocr-formula-v1` | `docling-local-ocr-v1` | 1, 2 |
| `doc54.pdf` | `docling-no-ocr-formula-v1` | `docling-naver-ocr-v1` | 4, 10, 13, 14 |
| `doc7.pdf` | `docling-no-ocr-formula-v1` | `docling-local-ocr-v1` | 1, 2, 6 |
| `doc9.pdf` | `docling-no-ocr-formula-v1` | `docling-local-ocr-v1` | 4, 5, 7, 8 |

## 근거 위치 표기 규칙

- PDF/PPTX: Docling의 1-based `page_no`, 원본 `bbox`, 좌표 원점, `charspan`, `item_ref`를 함께 기록했다.
- 표: `item_ref`와 Docling `table_cells`의 0-based 시작·끝 행/열 및 셀 원문을 기록했다.
- DOCX/XLSX: page provenance가 없으면 원본 SHA-256 + Docling JSON SHA-256 + `item_ref`를 정규 위치로 사용했다.
- 인용문: 공백 정규화 외에는 raw `document.docling.json` 항목 또는 선택 표 셀 안에 존재하는지 자동 검증한다.
- Retrieval 연결: 같은 source key의 chunk 안에 정확한 인용문이 포함된 경우만 chunk ID, canonical document ID, content hash, page 범위를 기록했다.

## 검증 절차

1. Google Drive 전달 폴더와 원본 폴더에서 158개 파일 ID·URL·크기를 확인했다.
2. 로컬 전달 archive와 분할 파일을 Drive `SHA256SUMS`와 대조했다.
3. 모든 사용 원본의 바이트 크기·SHA-256과 variant별 bundle manifest를 다시 계산하고, delivery loose bundle이 archive member와 byte-identical한지 확인했다.
4. 각 필수 주장을 raw Docling item·표 셀·page/bbox/charspan에 대조하고, review_local_ocr 근거 페이지는 원본 PDF 렌더로 시각 확인했다.
5. FAQ 답변과 제공 문서가 충돌하거나 문서가 부족한 경우 문서 기준으로 범위를 줄이고 금지 주장을 기록했다.
6. 질문 순서, 86개 ID, 레지스트리 참조, artifact hash, 원문 인용과 retrieval 연결을 validator로 재검증했다.

## 재현 명령

```bash
uv run python -m evals.harness.validate_miraeasset_gold --structure-only
uv run python -m evals.harness.validate_miraeasset_gold --data-root data
uv run pytest -q tests/evals/test_miraeasset_gold.py
```

CI에는 대용량 원본과 Docling bundle이 없으므로 구조·해시는 `--structure-only`로 확인한다. 전체 검증은 Drive 전달물과 byte-identical한 로컬 `data/` 스냅샷에서 수행한다.
