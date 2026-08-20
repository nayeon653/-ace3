# Agent 그래프 생성과 검수

Main Supervisor와 세 Domain Agent의 현재 LangGraph 구조는 저장소 루트에서 다음 명령으로
생성한다.

```bash
make agent-graph
```

생성 결과는 [`../architecture/agent-graphs.md`](../architecture/agent-graphs.md)와
`docs/architecture/generated/`의 PNG 파일에 저장된다. 컴파일 그래프는 LangGraph의
`get_graph(xray=True)` 결과를 사용한다. Mermaid.ink와 호환되지 않는 대괄호 포함 node
label만 따옴표로 감싼 뒤, LangChain의 `draw_mermaid_png()`가 제공하는 Mermaid.ink 방식으로
PNG를 변환하므로 별도 Mermaid CLI나 브라우저를 설치할 필요가 없다.

생성 스크립트는 실제 제품 Factory를 사용하지만 테스트용 모델과 실행 불가능한 검색 대체
객체를 주입한다. 따라서 HCX API key, Qdrant와 `.env`는 필요 없고 모델이나 검색을 실제
호출하지 않는다. PNG 생성 시에는 Mermaid 문법만 Mermaid.ink에 전송하며 프롬프트, 상태,
질문, 문서 내용과 시크릿은 포함하지 않는다.

전체 호출 구조는 런타임과 공유하는 Domain Agent 등록 정보에서 Tool 호출 경계를 만들고,
각 상세 이미지는 `CompiledStateGraph` 결과를 그대로 변환한다. Middleware, Tool 또는 Domain
Agent 등록이 바뀌면 다시 생성해 코드 변경과 같은 PR에 포함한다. LangGraph 밖의 검색·Provider
경계가 바뀌면 생성 스크립트의 전체 호출 구조 선언도 함께 수정한다.

현재 문서가 코드와 일치하는지만 확인하려면 다음 명령을 사용한다.

```bash
make agent-graph-check
```

이 검사는 외부 네트워크를 사용하지 않는다. Mermaid 원본의 SHA-256 manifest, PNG 파일 집합과
문서를 현재 코드에서 만든 결과와 비교한다. 일반 테스트도 같은 검사를 수행하므로 갱신 누락을
검출한다.
