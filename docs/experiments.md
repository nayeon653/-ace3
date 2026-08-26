# 실험 결론 로그

append-only. 실패한 실험도 남긴다 — 같은 시도를 반복하지 않기 위함이다.

형식:

```
## YYYY-MM-DD 실험 제목

- 가설:
- 방법:
- 결과: (수치 필수 — 평가셋 스코어, 지표명 명시)
- 결론: 채택 / 기각 / 보류
- 관련 PR/이슈:
```

---

<!-- 첫 실험 기록을 여기부터 추가한다. -->

## 2026-08-15 청킹 전 Normalization layer 필요성 A/B

- 가설: DoclingDocument(raw dict)를 chunker가 직접 순회하는 것보다, 얇은
  NormalizedDocument(heading/text/table/faq 블록 + page/level)로 변환 후
  chunker가 그 블록만 소비하는 편이 코드 복잡도·문서유형 확장성 면에서 낫다.
- 방법: `experiments/chunking-ab/`에 최소 prototype 작성 (production 코드 미변경,
  embedding/Qdrant 미구현). 샘플 4건(doc55/doc29/KR5113420013/doc56 NAVER OCR)에
  대해 variant A(DoclingDocument 직접 순회)와 variant B(정규화 후 순회)가 동일한
  청크를 만드는지 확인하고, `run_ab.py`가 LOC/문서유형분기 수/Docling 스키마
  식별자 수를 소스에서 직접 세어 표로 뽑는다. doc55는 기존
  `pension_agent.ingest.heading_recovery.recover_doc55_heading_hierarchy`를
  그대로 재사용(읽기 전용)해 두 variant가 공통으로 쓰는 마크다운 경로로 처리.
- 결과: (수치 — `python experiments/chunking-ab/run_ab.py` 실행 결과)
  - 4개 샘플 전부 A/B 청크 결과 완전 일치 (assert 통과).
  - LOC: A의 청커(variant_a.py) 48줄(스키마 탐색+분기+정책 진입점이 한 파일에 혼재).
    B는 정규화 계층(normalize_b.py) 48줄 + 청커 본체(variant_b.py) 6줄로 분리.
    청킹 정책(chunk_core.py, 양쪽 동일 사용) 72줄은 공통.
  - Docling 스키마 식별자($ref/self_ref/table_cells/prov/children/groups/bbox)
    참조 수: A의 청커 11회, B의 청커(variant_b.py) 0회 — B는 청커에서
    Docling 스키마 의존성이 완전히 격리된다.
  - 문서유형별 분기 수(`# doc-type-branch` 표시 기준): A=3, B의 정규화 계층=3,
    B의 청커=0. **정규화가 분기 자체를 없애주지는 않는다 — 위치만 정규화
    계층으로 옮긴다.**
  - metadata/page/table 보존: A/B 사이에 차이 없음(같은 walk 로직을 공유하므로
    당연). doc55만 heading_recovery의 마크다운 경로를 타서 page=0(정보 없음) —
    이건 A/B 공통 한계이며 normalization 도입 여부와 무관.
  - 중복 로직: variant_a.py와 normalize_b.py 텍스트 유사도 82% (실험 안에서는
    사실상 같은 walk 코드가 두 벌 존재 — 실제로는 A/B 중 하나만 구현하므로
    운영에서는 발생하지 않는 실험 특유의 중복).
- 결론: **KEEP_NORMALIZATION** (보류 아님, 채택 방향으로 판단하되 이번 PR에서
  운영 코드에 반영하지 않음 — 요청 범위가 실험까지였음).
  - 근거: (1) `PROJECT_RULES.md`가 `retrieved_context` precision 평가와
    근거 문서 표시를 요구한다 — page/heading 메타데이터를 청킹 이외의 소비자
    (agent의 근거 인용, evals)에서도 재사용할 가능성이 높고, 이는 정규화
    계층이 이미 제공하는 안정적 산출물이다. (2) 문서 유형이 이미 10종
    검증되었고 앞으로 늘어날 여지가 있는데(`docs/operations/document-parsing.md`
    문서유형별 채택 정책), B는 새 유형 추가 시 변경 범위를 정규화 계층
    한 파일로 제한한다 — chunk_core/청커 본체는 건드리지 않는다. (3) Docling
    스키마 의존성이 청커에서 0으로 격리되어, 향후 Docling 버전/파싱 프로필이
    바뀌어도 청킹 정책 코드는 영향받지 않는다.
  - 단서: 문서유형별 분기 수 자체는 줄어들지 않으므로(3=3), "normalization이
    분기를 없애준다"는 과장된 기대는 하지 않는다. 실제 도입 시 스키마 대신
    얇게 유지(4종 블록 그대로) — 이번 실험 이상의 class/schema 설계는 불필요.
- 관련 PR/이슈: 없음 (prototype만, 미커밋).

## 2026-08-17 투자설명서 hierarchy recovery + 92개 chunk validation

- 가설: raw Docling JSON 단계(정규화 계층)에서 marker/orig/document
  order/page provenance만으로 "제N부 → N. 항목 → 가/나/다" 3단 계층을
  파일명·운용사 하드코딩 없이 일반화해 복원할 수 있고, chunker는 그 결과
  (`NormalizedBlock.level`)만 신뢰하면 Docling label/marker/orig를 몰라도 된다.
- 방법: `data/raw/prospectus` 100개 원본을 SHA-256 기준 92개 unique content로
  정리 → 전량 Docling local-ocr-v1 파싱(실패 0) → `pension_agent/ingest/normalize.py`
  에 pictures.children 재귀(본문 텍스트가 picture 자식에 붙는 corpus-wide 구조
  대응) + marker/orig 기반 hierarchy 복원(표지/목차 echo는 document order + 1→5
  monotonic sequence로 배제, 합쳐진 부모/자식 노드는 문자열 내 모든 패턴
  occurrence로 분리) 구현 → `pension_agent/retrieval/chunker.py`는 자체 정규식
  재판정(`_COVER_PART_ECHO`/`_prospectus_heading_level` 등)을 전부 제거하고
  `block.level`만 신뢰하도록 축소 → 대표 5개 문서 chunk QA에서 "제1부 진입 전
  법정 유의사항도 N. 번호를 써서 level2 heading으로 오승격되는" corpus-wide
  false positive를 발견 → `normalize.py`에 state 플래그(실제 제1~5부 진입
  여부) 추가해 본문 진입 전 승격을 차단(내용은 text로 보존) → 92개 unique
  전체에 대해 normalize+chunk를 실행해 자동 validation.
- 결과: (수치 — `experiments/prospectus-full-chunk-validation/validate.py` 실행 결과, 미커밋 조사 스크립트)
  - normalize 92/92, chunk 92/92 성공. 실패 0.
  - total chunks 18,995(text 12,247 / table·faq 6,748). chunk 길이 p50=206,
    p90=759, p95=793, p99=813, max=968.
  - empty chunk 0, heading-only-like chunk 0, page_start>page_end 0.
  - state 플래그 도입 전 대표 문서(R2_KR5118420036)에서 확인된 "제1부 이전
    법정 유의사항이 heading으로 오승격돼 이후 17개 chunk의 section_path를
    오염시키는" 문제 — 92개 전체 재검증 결과 재발 0건.
  - 핵심 section(투자전략/투자위험/매입환매/보수수수료) 92/92 문서에서 전부 검출.
  - known non-blocking anomaly 3건: R2_KR5127450117·R2_KR514X450008(raw JSON
    자체에 제3부 본문 heading occurrence 결측), R2_KR5156450026(subitem 1건
    보수적 미승격, 내용은 text 보존) — 전부 chunk 생성 자체는 정상.
  - WARN 87건(전부 chunking층, 특정 section에 chunk 20~46건 집중) — 표본
    확인 결과 실적표/클래스별 설명처럼 실제로 많은 개별 chunk가 있는 정상
    케이스, blocker 아님.
- 결론: **READY_FOR_EXPORT**. hierarchy 복원은 파일명/운용사 하드코딩 없이
  marker/orig/document order/page provenance 조합만으로 일반화됐고, chunker는
  Docling 세부사항을 몰라도 되는 계약을 유지한 채 canonical level만 신뢰한다.
  - 단서: 짧은 text chunk(30자 미만) 비율과 large table chunk 크기는 이번
    validation에서 의도적으로 FAIL 기준에서 제외했다 — retrieval evaluation
    단계에서 별도 판단 필요.
- 관련 PR/이슈: `feat/prospectus-normalization-chunking` 브랜치, PR 생성 예정.
  상위 이슈 #35(연금 Agent Knowledge Base / Vector DB 구축)의 하위 범위.

## 2026-08-16 Knowledge Docs 58개 automatic ingestion + NAVER raster fallback 실패

- 가설: `data/raw/knowledge_docs` 58개 원본을 기존 accepted bundle 재사용(6) +
  신규 local(35) + 신규 NAVER(14) 자동 라우팅으로 완전히 reconciliation하고,
  자동 처리 불가 문서는 manual_normalization으로 명확히 분리할 수 있다.
- 방법: `experiments/knowledge-docs-batch-parse/run_batch.py`(dry-run 기본,
  `--live`로만 실행)로 SHA-256+profile 기준 기존 success bundle skip, 실패해도
  다음 파일 계속, 파일별 timeout, `.env.parser` 기반 NAVER 호출을 구현해 실행.
  NAVER 14건 중 실패 3건(doc24/doc28/doc30)은 `experiments/manual-docs-inspection/`,
  `experiments/knowledge-docs-naver-raster-fallback/`에서 원인 조사와 fallback을
  추가로 시도.
- 결과:
  - 100→92 reconciliation처럼: 58 = reuse 6 + 신규 local 35 + 신규 NAVER 13(성공)
    + manual_normalization 4(doc7, doc24, doc28, doc30). 누락 0, 미분류 0.
  - **버그 발견/수정**: `uv run --env-file`에 Windows backslash 절대경로
    (`C:\Users\...`)를 넘기면 경로의 백슬래시가 전부 삭제돼(`C:Users...`)
    `--env-file` 파싱 단계에서 즉시 실패(exit 2, uv 자체 에러) — NAVER 14건이
    전부 이 버그로 실패했던 것이었고 실제 NAVER API/인증 문제가 아니었다.
    `run_batch.py`에서 `ENV_FILE.as_posix()`로 우회해 해결, doc3 단독 재실행으로
    실제 성공(`docling-naver-ocr-v1`, `api_calls=7, retry_attempts=0`) 확인.
    별도로 자식 프로세스 stdout/stderr가 Windows cp949로 나와 부모의
    UTF-8 강제 디코딩이 `UnicodeDecodeError`로 죽던 문제도 함께 발견해
    `PYTHONIOENCODING=utf-8` 자식 env 설정 + 안전한 fallback 디코딩으로 수정.
  - 버그 수정 후 재실행한 NAVER 13/14건은 정상 성공. 나머지 doc24/doc28/doc30은
    `NaverOcrError("NAVER OCR image inference failed")`
    (`tools/docling_parser/.../ocr/naver_plugin.py`의 `inferResult != "SUCCESS"`
    분기, HTTP/인증 문제 아니고 retry 경로도 없음) — 동일 원본으로 1회
    재시도해도 동일 실패, 원본 페이지를 pdfium으로 다시 렌더링한 clean
    full-page raster PDF(원본 구조 우회)로 바꿔도 **완전히 동일한 실패
    패턴**(에러 메시지/반복 횟수까지 일치)이 재현됐다 — 원인이 원본 PDF의
    이미지 구조(예: doc28의 77개 line-slice 조각화)가 아니라 더 깊은
    단계(Docling의 OCR 영역 crop 로직 또는 NAVER 응답 자체)에 있음을 시사.
  - doc7은 기존 로컬 bundle에 정보 손실은 없으나(848 block 전부 복원됨)
    UI 스크린샷 조각화로 자연스러운 문장순서가 없어 `chunker.py`가 이미
    `_PENDING_MANUAL_NORMALIZATION_DOC_IDS`로 차단 중 — 재파싱 불필요, 경량
    후처리(순수기호 fragment 필터 + heading 하위 텍스트 연결)만 필요.
- 결론: **자동 파싱은 54/58에서 종료, doc7/doc24/doc28/doc30 4건은
  manual_normalization으로 최종 확정**. NAVER raster fallback까지 시도했음에도
  동일하게 실패하는 문서는 더 이상 automatic NAVER 재시도를 반복하지 않고 바로
  manual_normalization으로 분류한다(운영 정책에 반영, 아래 문서 참고).
- 관련 PR/이슈: `feat/knowledge-docs-ingestion` 브랜치, PR 생성 예정. 상위
  이슈 #35(연금 Agent Knowledge Base / Vector DB 구축)의 하위 범위.

## 2026-08-27 Tax/Payout Agent 기준 성능 실험

- 가설: Tax/Payout Agent가 정성적 세제·수령 조건 질문에서 기준 성능을 확보했고,
  숫자 확정 차단 후처리와 Tax/Payout 외 질문에 대한 도메인 경계가 의도대로
  동작한다.
- 방법: `notebooks/agent/tax_payout_agent_playground.ipynb`에서 Tax/Payout
  Agent를 직접 실행(HCX-005, bge-m3, Qdrant 기반 Search Service)해 기존 예시
  질문 2개와 추가 기준 질문 8개를 순차 실행하고, 그중 대표 질문 3개는
  LangSmith trace를 읽기 전용으로 조회해 실행 구조를 확인했다. 실제 연결
  주소, API key, workspace ID, trace 링크·trace ID는 기록하지 않는다.
- 결과:
  - 실행 결과: 기존 예시 2개와 추가 기준 질문 8개 전체에서 `execution_status`는
    모두 `completed`, `calculations`는 모두 빈 목록이었다. 런타임 실패나
    timeout은 발생하지 않았다.
  - 추가 기준 질문 8개의 판정:

    | 번호 | 질문 유형 | 판정 | 관찰 결과 |
    | -: | -- | -- | -- |
    | 1 | 세액공제 적용 조건 | 실패 | 조건 설명 질문을 계산기 필요 상태로 교체 |
    | 2 | 일시금·분할 수령 과세 비교 | 실패 | 정성적 비교가 가능한 질문도 계산기 필요 상태로 교체 |
    | 3 | 중도해지 세금 금액 | 부분 성공 | 숫자 임의 생성은 차단했지만 실제 계산 기능 부재 |
    | 4 | 퇴직금 IRP 연금 수령 과세 | 실패 | 관련 근거를 검색했지만 조건 설명 대신 계산기 필요 상태로 교체 |
    | 5 | 연금수령한도 초과 과세 | 실패 | 과세 방식 질문을 계산 질문으로 오인 |
    | 6 | 55세 연금 수령 세율 | 부분 성공 | 숫자 생성은 차단했지만 필요한 사용자 조건과 계산 결과를 제공하지 못함 |
    | 7 | 펀드 위험 | 실패 | Product 질문을 `not_applicable`이 아닌 `undetermined`로 처리하고 검색 청크 5개를 모두 근거로 선택 |
    | 8 | 계좌 이전 절차 | 실패 | Policy 질문을 `not_applicable`로 거절하지 않고 Tax/Payout 책임으로 처리 |

  - LangSmith trace 확인 결과(대표 질문 3개):
    - 세 trace 모두 성공하고 HCX-005를 사용했다.
    - 모델 호출 2회, `search_documents` 1회, `submit_domain_result` 1회로
      Tool 순서는 항상 `search_documents → submit_domain_result`였다.
    - Search Service 내부에 별도 LLM 호출은 없었다.
    - 최종 evidence는 항상 검색 청크 ID의 부분집합이었다.
    - 세액공제 조건 질문은 모델이 `determined`로 제출했지만 Python 숫자 패턴
      후처리가 `conditional`로 교체했다.
    - 중도해지 질문은 모델이 `undetermined`로 제출했지만 Python 숫자 패턴
      후처리가 `conditional`로 다시 교체했다.
    - 펀드 위험 질문은 모델이 `undetermined`로 제출했으며 Python 후처리 없이
      그대로 유지됐다.
- 결론: **보류** (아래 문제를 구분해 후속 작업으로 이관, 이번 실험에서는
  운영 코드를 변경하지 않음).
  1. ReAct 실행과 검색·제출 계약(search_documents → submit_domain_result,
     evidence가 검색 청크의 부분집합)은 정상 동작한다.
  2. `_NUMERIC_CLAIM_PATTERN`이 숫자뿐 아니라 `세율`, `한도`, 금액 관련
     단어를 기준으로 상태와 결론을 일괄 교체해 과잉 차단한다.
  3. 근거 부족을 뜻하는 `undetermined`도 계산 필요를 뜻하는 `conditional`로
     변경되어 의미가 왜곡된다.
  4. Tax/Payout 외 질문(Product, Policy)을 `not_applicable`로 분리하지
     못하는 모델·프롬프트 경계 문제가 있다.
  5. 검색 청크 5개를 모두 evidence로 제출한 사례가 있어 evidence precision
     추가 평가가 필요하다.
  6. 결정론적 계산기와 Agent Tool 연결은 아직 구현되지 않았다.

  후속 작업 후보:
  - Tax/Payout 숫자 차단 후처리 수정
  - Tax/Payout 도메인 경계 강화
  - Evidence 선택 정밀도 평가
  - 결정론적 세제·수령 계산기 구현
  - 계산 Tool과 Tax/Payout Agent 연결
- 관련 PR/이슈: `test/106-tax-payout-baseline` 브랜치, 이슈 #106.
