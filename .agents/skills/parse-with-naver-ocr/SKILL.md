---
name: parse-with-naver-ocr
description: -ace3 저장소의 PDF, DOCX, PPTX, XLSX 파일을 고정 NAVER CLOVA General OCR V2 프로필로 파싱할 때 사용한다. 현재 사용자 요청에서 NAVER OCR을 명시적으로 지정했거나 해당 문서 이미지의 NAVER Cloud 외부 전송을 명시적으로 승인한 경우에만 사용한다.
---

# NAVER OCR 파싱 진입점

이 파일에서 상위 디렉터리를 탐색해 `docs/operations/document-parsing.md`와
`tools/docling_parser/pyproject.toml`이 모두 있는 저장소 루트를 찾는다. 중앙 운영
문서를 끝까지 읽고 **NAVER OCR 실행** 절차를 그대로 따른다.

현재 요청에서 NAVER OCR 지정 또는 해당 범위의 외부 전송 승인이 모두 없으면 중단하고
로컬 OCR Skill을 사용한다. 명령, 옵션, 저장·검수 정책을 이 Skill에 복제하지 않는다.
중앙 문서를 찾지 못하거나 내용이 충돌하면 추측하거나 다른 파서로 우회하지 말고
설정 오류를 보고한다.
