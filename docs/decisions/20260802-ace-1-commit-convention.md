---
status: accepted
date: 2026-08-02
type: process
related:
  - https://app.notion.com/p/3ac8385edd508146aab6eeea04355bce
supersedes: []
superseded-by: []
---

# 가벼운 Conventional Commits 형식을 채택

## 배경

기존 커밋 형식인 `[type] #이슈번호 작업 내용`은 실제로 생성하지 않는 이슈 번호를
항상 요구했다. 프로젝트 전용 문법을 유지할 필요에 비해 커밋 작성 비용과 범용 도구
연동 제약이 컸다.

## 결정

- 커밋 제목은 `<type>[optional scope][!]: <description>` 형식을 사용한다.
- scope와 본문은 필요할 때만 사용하고 설명은 한국어를 허용한다.
- 이슈 번호는 실제 이슈가 있을 때 본문이나 footer에 선택적으로 기록한다.
- `exp`는 실험 커밋을 위한 사용자 정의 type으로 유지한다.
- `hotfix` 대신 `fix`를 사용한다.
- `.githooks/commit-msg`에서 허용 type과 제목 형식을 검증한다.
- squash merge 시 최종 커밋 또는 PR 제목이 규칙을 따르도록 한다.

## 고려한 대안

- 기존 규칙은 작은 팀에서 읽기에 충분하지만 이슈 번호 강제와 프로젝트 전용 문법을
  계속 유지해야 하므로 채택하지 않았다.
- changelog와 버전 배포까지 자동화하는 엄격한 적용은 대회 제출용 프로젝트 규모에
  비해 설정 비용이 커서 도입하지 않았다.

## 결과

- 커밋 기록의 변경 유형과 선택적 범위를 일관된 위치에서 확인할 수 있다.
- 범용 commit lint, changelog, release 도구를 추후 연결하기 쉽다.
- 팀원은 허용 type과 `!`의 의미를 알아야 하며, 프로젝트의 `exp` 확장을 공유해야 한다.

## 관련 자료

- [ACE-1: 커밋 메시지 형식을 Conventional Commits로 변경 검토](https://app.notion.com/p/3ac8385edd508146aab6eeea04355bce)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- `docs/CONVENTIONS.md`
- `.githooks/commit-msg`
