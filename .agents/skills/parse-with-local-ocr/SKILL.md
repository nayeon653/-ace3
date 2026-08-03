---
name: parse-with-local-ocr
description: -ace3 저장소의 PDF, DOCX, PPTX, XLSX 파일을 고정 로컬 EasyOCR 프로필로 파싱할 때 사용한다. 일반적인 문서 파싱, 파일, 폴더, 배치 요청에 기본으로 사용하며 사용자가 현재 요청에서 NAVER OCR이나 외부 전송을 명시하면 사용하지 않는다.
---

# 로컬 OCR 파싱 진입점

이 파일에서 상위 디렉터리를 탐색해 `docs/operations/document-parsing.md`와
`tools/docling_parser/scripts/parse_document.py`가 모두 있는 저장소 루트를 찾는다. 중앙 운영
문서를 끝까지 읽고 **로컬 OCR 실행** 절차를 그대로 따른다.

명령, 옵션, 저장·검수 정책을 이 Skill에 복제하지 않는다. 중앙 문서를 찾지 못하거나
내용이 충돌하면 추측하거나 다른 파서로 우회하지 말고 설정 오류를 보고한다.
