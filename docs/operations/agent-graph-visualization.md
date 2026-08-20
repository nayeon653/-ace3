# Agent 그래프 생성과 검수

Main Supervisor와 세 Domain Agent의 현재 LangGraph 구조는 저장소 루트에서 다음 명령으로
생성한다.

```bash
make agent-graph
```

생성 결과는 [`../architecture/agent-graphs.md`](../architecture/agent-graphs.md)에 저장된다.
GitHub가 문서 안의 Mermaid 블록을 그림으로 렌더링하므로 별도 Mermaid CLI나 브라우저를
설치할 필요가 없다.

생성 스크립트는 실제 제품 Factory를 사용하지만 테스트용 모델과 실행 불가능한 검색 대체
객체를 주입한다. 따라서 HCX API key, Qdrant, `.env`와 외부 네트워크 없이 동작하며 모델이나
검색을 실제 호출하지 않는다.

전체 호출 구조는 서로 독립적으로 컴파일된 Main Supervisor와 Domain Agent 사이의 Tool 호출
경계를 보여준다. 이어지는 네 그래프는 각 `CompiledStateGraph.get_graph()` 결과를 그대로
Mermaid로 변환한 것이다. Middleware나 Tool 구성이 바뀌면 다시 생성해 코드 변경과 같은 PR에
포함한다.

현재 문서가 코드와 일치하는지만 확인하려면 다음 명령을 사용한다.

```bash
make agent-graph-check
```

일반 테스트도 생성 결과와 커밋된 문서를 비교하므로 갱신 누락을 검출한다.
