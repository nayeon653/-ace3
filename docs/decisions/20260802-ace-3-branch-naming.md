---
status: accepted
date: 2026-08-02
type: process
related:
  - https://app.notion.com/p/3ac8385edd5081319d74ddf491724ec2
supersedes: []
superseded-by: []
---

# 브랜치명을 유형과 작업 설명으로 단순화

## 배경

기존 `<type>/<owner>/#<issue>` 형식은 Notion 담당자, 커밋 author, PR 작성자와
작업자 정보를 중복 관리했다. 별도 이슈가 없는 작업에도 번호를 요구하고, 브랜치
목록만으로는 작업 내용을 알기 어려웠다.

## 결정

- 새 브랜치는 `<type>/<short-description>` 형식을 사용한다.
- 설명은 작업 결과를 나타내는 영문 소문자 kebab-case 명사구로 작성한다.
- 실제 GitHub 이슈가 있는 작업만 `feat/12-ocr-pipeline`처럼 번호를 붙인다.
- type은 커밋 컨벤션과 같은 목록을 사용한다.
- 이미 생성된 브랜치는 강제로 바꾸지 않는다.

## 고려한 대안

- 기존 형식은 작업자와 번호를 빠르게 필터링할 수 있지만 현재 관리 방식과 정보가
  중복되어 채택하지 않았다.
- 모든 브랜치에 이슈 번호와 설명을 넣는 형식은 실제 GitHub 이슈가 없는 작업에
  불필요한 번호를 만들게 하므로 선택적 규칙으로만 남겼다.

## 결과

- 원격 브랜치 목록에서 번호를 조회하지 않고 작업 목적을 파악할 수 있다.
- 작업 인계나 공동 작업 시 브랜치명을 변경할 필요가 없다.
- 담당자와 작업 상태는 Notion 및 GitHub에서 확인해야 한다.

## 관련 자료

- [ACE-3: 브랜치명을 type/short-description 형식으로 단순화](https://app.notion.com/p/3ac8385edd5081319d74ddf491724ec2)
- `docs/CONVENTIONS.md`
