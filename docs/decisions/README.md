# 결정 기록

프로젝트의 중요한 기술·프로세스 결정을 파일 단위로 보존합니다. 현재 적용되는
규칙은 `CLAUDE.md`와 `docs/CONVENTIONS.md`에 두고, 이 디렉토리에는 해당 규칙을
선택한 배경과 대안, 결과를 기록합니다.

## 작성 규칙

- 결정 하나당 파일 하나를 작성합니다.
- 파일명은 `YYYYMMDD-[issue-]short-description.md` 형식을 사용합니다.
- `type`은 `architecture`, `process`, `product`, `operations`, `project` 중에서
  선택합니다.
- `status`는 `proposed`, `accepted`, `superseded`, `rejected` 중에서 선택합니다.
- 채택된 기록은 오탈자, 링크, 상태 외에는 수정하지 않습니다.
- 결정이 바뀌면 새 기록을 만들고 새 기록의 `supersedes`와 이전 기록의
  `superseded-by`를 서로 연결합니다.
- 폐기되거나 대체된 기록도 삭제하거나 이동하지 않습니다.
- Notion 카드, GitHub 이슈·PR처럼 결정의 근거가 된 자료를 관련 링크에 남깁니다.

새 기록은 [TEMPLATE.md](TEMPLATE.md)를 복사해서 작성합니다.

전체 결정 목록과 현재 상태는 [INDEX.md](INDEX.md)에서 확인합니다.
