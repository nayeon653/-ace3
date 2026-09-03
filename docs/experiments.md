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

## 2026-08-27 Tax/Payout Agent 숫자 보호·도메인 경계 개선 (#108)

- 가설: `_NUMERIC_CLAIM_PATTERN`을 실제 숫자·%·단위 표현으로 좁히고, 필드별
  숫자 가드와 1회 정성적 재제출 유도, `not_applicable` 검색 선행 면제를
  추가하면 #106에서 발견한 화제어 오탐, `undetermined` 의미 손실, 도메인
  경계 실패가 해소되면서 기준 질문 8개 전체가 `execution_status: completed`로
  종료된다.
- 방법: `pension_agent/agent/tax_payout/react.py`의 `_NUMERIC_CLAIM_PATTERN`에서
  `세율`·`공제율`·`공제액`·`금액`·`한도` 화제어를 제거하고 숫자·%·퍼센트·
  프로·만원·억원만 남겼다. `_apply_numeric_claim_guard`로 conclusion·
  missing_conditions·warnings를 필드별로 검사해 `undetermined`는 어떤
  경우에도 `conditional`로 승격하지 않도록 분리했다. `submit_domain_result`에
  `numeric_resubmit_used` 상태를 추가해 숫자 포함 conclusion을 처음 제출하면
  즉시 대체하지 않고 1회 정성적 재제출을 요청한 뒤, 재제출에도 숫자가 남으면
  그때 안전 fallback을 적용하도록 바꿨다. `status == "not_applicable"`을
  `search_documents` 호출 여부 확인보다 먼저 처리해 도메인 외 질문은 검색
  없이 즉시 종료되게 했다. `pension_agent/prompts/domain/tax-payout-agent.md`에
  Product/Policy Agent 책임 경계와 최소 evidence 인용 지침을 추가했다.
  `tests/unit/agent/test_domain_agents.py`에 필드별 숫자 가드, `undetermined`
  보존, 1회 재제출, `not_applicable` 검색 생략을 검증하는 단위 테스트를
  추가했다. 개선 후에는 `notebooks/agent/tax_payout_agent_playground.ipynb`로
  HCX-005 + Qdrant 실제 연결에서 기존 예시 2개와 기준 질문 8개를 재실행하고,
  8개 전체를 LangSmith trace로 읽기 전용 조회해 모델·Tool 호출 횟수와 evidence
  선택을 확인했다. 실제 연결 주소, API key, workspace ID는 기록하지 않는다.
- 결과: (수치 — 재평가 실행 결과)
  - 개선 전(#106 기준): 기준 질문 8개 중 7개 `completed`, Q8은 실행 실패
    (failed).
  - 개선 후(#108, 이번 재평가): 기준 질문 8개 전체가 `execution_status:
    completed`. 예외(exception), 모델·Tool 호출 한도 초과, `submit_domain_result`
    3회 이상 반복 없음.
  - Q7·Q8(Product/Policy 영역 질문): `search_documents` 호출 없이 모델 호출
    1회·`submit_domain_result` 1회로 `not_applicable`로 즉시 종료.
  - Q3(중도해지 세금): 1차 제출에 숫자가 남아 재제출 요청을 받았고, 2차
    제출에서 숫자 없는 정성 결론으로 재작성되어 `determined`로 수락됨.
  - Q4(퇴직금 IRP 연금 수령 과세): 1차 제출에 숫자가 남아 재제출 요청을
    받았고, 2차 제출에서 숫자 없는 정성 결론으로 재작성되어 `conditional`로
    수락됨.
  - Q1·Q2·Q5·Q6: 1차 제출뿐 아니라 재제출 기회를 준 2차 제출에도 실제 숫자
    (세율·금액 등)가 남아 있어, numeric guard가 안전 fallback(`conditional` +
    "확정 수치 판단에는 결정론적 계산 Tool 결과가 필요합니다")으로 대체함.
    Q1은 이 과정에서 모델 호출이 4회 발생해 8개 중 가장 많았다.
  - 8개 전체에서 최종 evidence의 chunk ID는 예외 없이 해당 질문의
    `search_documents` 검색 결과 chunk ID 집합의 부분집합이었다.
- 결론: **채택**. #106에서 지적된 화제어 오탐, `undetermined` 의미 손실,
  도메인 경계 미비 문제를 해결했고 재평가에서 8개 전체가 `completed`로
  종료됨을 확인했다. 남은 한계:
  1. 결정론적 세제·수령 계산기(`pension_agent/rules/`)는 이번 이슈 범위 밖이며
     아직 구현되지 않았다 — 계산 Tool 결과가 필요한 질문(Q1·Q2·Q5·Q6)은
     여전히 `conditional` 안내로 그친다.
  2. Q1의 모델 호출 4회는 다른 질문(3회 이하) 대비 많아 향후 비용 최적화
     후보다 — 1차 제출 실패 후 모델이 자유 형식 텍스트로 응답해 tool 강제
     재프롬프트가 추가로 필요했던 경로다.
- 관련 PR/이슈: `fix/108-tax-payout-decision-quality` 브랜치, 이슈 #108.

## 2026-09-03 Policy/Tax 검색 식별자 기본값 개선 (#145)

- 가설: 검색 인자를 두 선택 필드의 JSON `null`에서 시작하고 명시된 식별자만
  치환하도록 안내하면, 질문의 주제·문장 전체를 파일명으로 전달하는 오류를 줄이면서
  사용자 지정 파일·청크 범위와 기존 문서 타입 권한을 유지할 수 있다.
- 방법:
  - 기준 커밋 `280469c`, 첫 후보 `89acc47`, 최종 평가 후보 `d0f5dd4`를 구분했다.
    실제 Uvicorn `GET /answer`에서 기존 HCX 모델과 Qdrant로 실행했다.
  - Policy/Tax 프롬프트와 `search_documents` 설명을 `null` 기본값 작성 →
    명시적 식별자 하나만 치환 → 전송 전 확인 → JSON 예시 순서로 정렬했다.
    유효 UUID가 우선이며, UUID가 없을 때 확장자를 포함한 정확한 파일명을 사용한다.
  - 범주 접두사와 주제는 `objective`에 남긴다. 문서 타입은 시스템이 적용하고
    파일명·UUID를 추측하거나 예시에서 복사하지 않도록 설명했다.
  - 실행 로직·권한 매핑·검색 횟수·후보 수·결과 수·모델 및 API 계약은 유지했다.
    Tax의 책임 범위 밖 검색 생략과 Product의 카탈로그 기반 파일 선택도 유지했다.
  - 질문셋 116문항을 각 1회 평가하고, 대표 5문항은 문항별 3회 관찰하도록 계획했다.
    일반 질문·명시적 파일·UUID·Product 경로의 대조군 8개를 별도로 실행했다.
  - 정답은 API에 보내지 않았다. 실제 답변과 반환 근거를 수동 평가하고,
    제공 원문으로 확인된 골든 오류는 별도로 표시했다. 모든 시도를 보존한다.
  - 검색 인자·실제 검색 결과·최종 인용 근거·최종 답변 품질을 별도 지표로 집계한다.
    개인 추적 정보, 질문 원문, 문서 원문과 실행 환경 비밀정보는 공개하지 않는다.
- 결과: **검색 인자 개선과 최종 답변 성능을 구분하여 판단한다.**

  기준 실행에서 파일명 오용은 116문항 중 13문항·14호출이었다. 실제 검색으로
  진행한 11호출은 모두 0청크였고, 나머지 3호출은 검색 요청 검증에서 거절됐다.
  MA-RP-026은 거절 후 다시 호출하여 두 집계에 포함되므로 문항 수를 합산하지 않는다.

  첫 후보는 기존 13문항에서 파일명 오용이 사라졌지만 확장 평가의 MA-PP-004에서
  범주를 파일명으로 전달하여 0청크가 재발했다. 당시 모델 입력은 첫 후보와 일치했다.
  따라서 해당 버전은 65개 응답에서 중단한 실패 실험으로 보존했다.
  HTTP·계약은 65/65 통과했으나 완전한 추적은 64/65이므로 검색 감사 분모는 64다.
  불완전한 추적 자체를 제품 검색 실패로 집계하지 않았다.
  이를 근거로 두 선택 필드를 명시적 `null`에서 구성하도록 두 번째 후보를 보강했다.

  **기존 파일명 오용 13문항의 동일 문항 비교 — 이 표는 전체 116문항 결과가 아니다.**

  | 지표 | 기준 실행 | `d0f5dd4`의 최초 응답 |
  | --- | ---: | ---: |
  | 최종 답변 정답 | 1/13 | 3/13 |
  | 최종 답변 부분 정답 | 1/13 | 4/13 |
  | 최종 답변 오답 | 11/13 | 6/13 |
  | 파일명·UUID 오용 문항 | 파일명 13/13 | 0/13 |
  | 실제 검색의 비어 있지 않은 결과 | 0/11 검색 호출 | 14/14 검색 호출, 각 5청크 |

  후보의 MA-PP-027은 두 도메인이 각각 검색하여 13문항에서 총 14회 검색했다.
  검색의 5청크 반환은 최종 인용의 적절성이나 정답을 뜻하지 않는다.
  아래 전수 결과에서 전체 정답 수 증가는 없었으므로 위 개선을 전체 답변 품질 향상으로 일반화하지 않는다.

  | 검증 범위 | 확정된 기준 또는 계획 | 최종 후보 결과 |
  | --- | --- | --- |
  | 전체 질문셋 | 116문항, 기준 정답 10·부분 42·오답 64 | 정답 10·부분 39·오답 67. 등급 상승 18·하락 22·유지 76 |
  | 검색 식별자·범위 | 실제 도구 입력과 검색 결과를 전수 대조 | 완전 추적 115문항에서 파일명·UUID 오용·검색 요청 검증 실패 0, 실제 검색 114회 모두 비어 있지 않음. 부분 추적 ISA001의 완료된 검색 2회도 정상 인자·각 5청크로 별도 확인 |
  | 문서 권한·모델·프롬프트 | 실제 실행 입력과 반환 타입을 확인 | 136개 HTTP 응답의 5필드 계약 및 요청 전후 버전 검사 통과. 완전 추적 135개(전수 115+반복 10+대조 10)의 관측 호출에서 권한·모델·프롬프트/도구 설명 불일치 0. 전수 ISA001은 모델 2개 미종료로 부분 추적 |
  | 도메인 실행 실패 | HTTP 성공과 별도 집계, 기준 23/116문항 | 완전 추적 115문항 중 16개. 별도 부분 추적 ISA001에서도 Policy 시간 초과 2회 확인(해당 문항 1개) |
  | 제공자 40009 오류 | 중복 조상 실행을 제외, 기준 15/116문항 | 완전 추적 115문항 중 11개; 부분 추적을 완전한 무오류 사례로 합산하지 않음 |
  | 반복 검증 | 대표 5문항, 문항별 3회; 모든 시도 보존 | 대표 5문항 총 15응답(최초 5+추가 10), 관측된 파일명·UUID 오용 0. 13응답에서 Policy/Tax 검색 실행; PP004의 2응답은 Product 경로로 변경 프롬프트 미실행. 판정 변동은 아래 표에 모두 보존 |
  | 대조군 | 일반·파일·UUID·Product 8개, 기본 실행 HTTP·계약 8/8 | 8종·10시도: 범위 검증 성공 9, Policy 파일 A1 도메인 미호출 1. 실제 검색 9회 모두 지정 범위/권한 유지; Product 단일 코드와 100개 카탈로그 경로 유지 |
  | Policy 파일 대조 추가 | A1은 도메인 미호출로 범위 미검증; A2·A3 추가 | 두 추가 시도 모두 doc4.pdf·chunk_id=null, Policy 권한으로 해당 파일의 참고자료 5청크 반환. A1은 미실행으로 보존 |
  | 기존 정답의 회귀 | 문항별 원인과 변경 범위의 관련성을 확인 | 기존 정답 10개 중 6개 유지, POLICY-005·MA-PP-022 부분 회귀, MA-PP-005·MA-RP-013 오답 회귀. 네 사례 모두 전후 파일·UUID 인자 null; 적용 대상 오독·조건 누락·Main의 새 주장 생성이 관찰됨. 파일 필터 변경이 직접 원인이라는 증거는 없으며 간접 영향과 모델 변동은 분리 입증하지 못함 |

  대조군에서 필요한 도메인·도구가 호출되지 않은 경우는 범위 검증 성공으로 세지 않는다.
  전수 평가의 최초 응답은 반복 실행으로 교체하지 않으며 대조군을 정답셋 분모에 합치지 않는다.


  **전체 최종 인용 근거 지표:** 기준 210개 중 관련 131(62.4%)·답변 지지 94(44.8%),
  후보 250개 중 관련 157(62.8%)·답변 지지 107(42.8%). 이는 최종 API 인용 기준이며
  검색 후보 전체의 정밀도나 재현율이 아니다.

  대표 검색 실패의 직접 회수 확인: PP007은 ISA 전환 절차의 doc33 청크가 검색 1위,
  PP014는 해지 후 과세재원 변경 예외의 doc5 청크가 검색 3위에 포함됐다.
  PP014의 최종 오답은 이 관련 근거가 미검색됐기 때문이라고 볼 수 없다.

  ISA001은 156.579초 뒤 HTTP 200으로 답했지만 Policy가 두 번 시간 초과됐다.
  재수집 후에도 모델 2개에 종료 기록이 없어 완전 추적 분모에서 제외했다.
  완료된 두 검색의 정상 인자·권한·각 5청크와 도메인 시간 초과는 관찰 사실로 별도 보존한다.
  이 부분 추적을 완전 검증 성공으로 합산하지 않았다.

  **대표 질문의 모든 응답 판정:**

  | 문항 | 최초 응답 | 추가 2회차 | 추가 3회차 |
  | --- | --- | --- | --- |
  | MA-PP-004 | 부분 정답 | 부분 정답 | 오답 |
  | MA-PP-007 | 부분 정답 | 부분 정답 | 부분 정답 |
  | MA-PP-014 | 오답 | 오답 | 오답 |
  | MA-RP-010 | 정답 | 부분 정답 | 부분 정답 |
  | MA-RP-039 | 오답 | 오답 | 오답 |

  대조군의 검색 범위 성공은 최종 답변의 정확성을 뜻하지 않는다. Policy 파일 A2/A3도
  검색 후 Main에서 근거와 다른 기한 설명을 추가했다. Tax 파일/UUID 대조 2개는
  검색이 정상이어도 이후 도메인 실행이 실패했다.

  평가 종료 시 Qdrant는 19,747 points·green으로 유지됐으며 기준 산출물 79개는
  SHA-256이 모두 같았다. 평가용 서버는 모든 요청 완료 후 종료했다.

  `d0f5dd4`의 CI 테스트는 1,059 passed·1 skipped이며 Qdrant smoke도 통과했다.
  Ruff 검사·포맷 확인과 mypy 93개 소스 파일 검사를 통과했다.
  wheel에 포함된 두 프롬프트 리소스가 소스와 바이트 단위로 일치함을 확인했다.

  기준 실행에는 새 평가기의 요청 전후 버전·소스 해시·health 검사 필드가 없다.
  따라서 새 guard의 116개 결측을 실제 버전 불일치나 제품 실패로 세지 않는다.
  기준 커밋과 실제 프롬프트·모델 입력은 확인했지만 새 후보와 동일 수준의
  요청별 실행 무결성을 소급 증명한 것으로 해석하지 않는다.
- 결론: **검색 인자 수정안으로 리뷰를 요청한다. 전체 답변 품질 개선은 확인되지 않았다.**
  기존 오류 13문항의 검색은 복구됐으나 최종 오답 6개가 남았다. 전수·반복·대조의
  관측 검색에서 식별자 오용은 재발하지 않았다. 답변 해석·합성 회귀는 별도 개선 과제다.
  검색된 근거의 적용 범위 오독, 일반 상품의 카탈로그 처리, `not_applicable`에 따른
  답변 소실과 Main 합성 문제는 별도 원인으로 기록하며 검색 프롬프트 효과와 혼합하지 않는다.
- 관련 PR/이슈: #145, PR #146. #143은 별도 실행·원인의 관련 분석이며
  이번 실험 통계에 합산하지 않는다.

## 2026-09-03 #145 평가 등급 일관성 정정과 PR 범위 대조

- 가설: 전후 답변이 동일한 문항에 서로 다른 등급을 적용하면 관측 회귀 수를
  과대 집계할 수 있다. 검색 인자 변화와 검색 후 판단 오류도 구별해야 한다.
- 방법: 보존된 기준 `280469c`와 후보 `d0f5dd4`의 실제 응답·골든·추적을 대조했다.
  API를 추가 호출하지 않았으며 이전 실험 기록과 원래 판정 파일은 보존했다.
- 결과:
  - POLICY-001은 질문·골든·최종 답변이 전후 완전히 동일하지만, 기준은 부분 정답,
    후보는 오답으로 평가됐다. 같은 조건 누락에 고정된 기준 평가를 적용하여 후보도
    부분 정답으로 정정한다. 최종 인용 근거의 개수 변화는 별도 지표로 유지한다.
  - 이 한 건의 판정만 정정한 후보 집계는 **정답 10·부분 정답 40·오답 66**이다.
    전후 등급 변화는 **상승 18·하락 21·유지 77**이다. 앞선 기록의 10/39/67과
    18/22/76을 대체하는 정정이며, 새 API 실행이나 전체 116문항 재채점 결과가 아니다.
    등급 하락 수는 프롬프트 변경으로 발생한 회귀의 인과 추정치가 아니다.
  - 기존 파일명 오용 13문항의 정상화와 완전 추적 115문항의 검색 인자·권한 감사
    결과는 그대로다. 기존 정답 10문항 중 4문항의 하락 판정도 바뀌지 않는다.
  - 네 하락 문항은 전후 파일명·UUID 인자가 모두 null이었다. MA-RP-013은 검색
    질의와 청크 5개도 동일하고 순서만 바뀌었다. 문서 적용·조건 전달 오류는
    관찰했지만 변경 프롬프트의 간접 영향과 모델 출력 변동은 분리하지 못했다.
  - MA-PP-020·MA-RP-014·MA-RP-017은 Product만 실행되어 변경된 Policy/Tax
    프롬프트가 실행되지 않았다. 이 경로의 문제를 이번 수정의 회귀로 귀속하지 않는다.
- 결론: **검색 인자 수정안으로 리뷰를 요청한다.** 필터 선택 개선과 관측된 답변
  품질 변화를 함께 공개한다. 전체 답변 품질 유지나 간접 영향 부재를 새로 입증한
  것으로 해석하지 않으며, 변경된 검색 지시의 영향이 재현되면 해당 범위에서 보완한다.
- 관련 PR/이슈: #145, PR #146.
