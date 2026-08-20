# Agent 전체 그래프

<!-- 이 파일은 tools/render_agent_graphs.py로 생성됩니다. 직접 수정하지 마세요. -->

`make agent-graph`로 현재 코드에서 PNG와 함께 다시 생성합니다. 컴파일 그래프는 LangGraph의 `get_graph(xray=True)` 결과를 사용합니다.

## 전체 호출 구조

![전체 호출 구조](generated/agent-system.png)

<details>
<summary>Mermaid 원본 보기</summary>

```mermaid
flowchart TB
    question["GET /answer 질문"] --> supervisor

    subgraph main["Main Supervisor · CompiledStateGraph"]
        supervisor["HCX-005 model"] <--> domain_tools["Domain Agent tools"]
    end

    domain_tools -->|analyze_policy| domain_policy
    domain_tools -->|analyze_tax_payout| domain_tax_payout
    domain_tools -->|analyze_product| domain_product

    subgraph domains["Domain Agents · 각각 CompiledStateGraph"]
        domain_policy["Policy Agent"]
        domain_tax_payout["Tax/Payout Agent"]
        domain_product["Product Agent"]
    end

    domain_policy --> domain_tools
    domain_policy --> search_tools
    domain_tax_payout --> domain_tools
    domain_tax_payout --> search_tools
    domain_product --> domain_tools
    domain_product --> search_tools

    subgraph search["공용 검색 경로"]
        search_tools["search_documents"] --> search_service["SearchService"]
        search_service --> embedding["CLOVA bge-m3 query embedding"]
        search_service --> qdrant["Qdrant hybrid retrieval"]
    end

    supervisor --> answer["최종 답변"]
```

</details>

## Main Supervisor 컴파일 그래프

![Main Supervisor 컴파일 그래프](generated/main-supervisor.png)

<details>
<summary>Mermaid 원본 보기</summary>

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	model("model")
	tools("tools")
	SupervisorModelCallLimit\2ebefore_model("SupervisorModelCallLimit.before_model")
	SupervisorModelCallLimit\2eafter_model("SupervisorModelCallLimit.after_model")
	ToolCallLimitMiddleware\5banalyze_policy\5d\2eafter_model("ToolCallLimitMiddleware[analyze_policy].after_model")
	ToolCallLimitMiddleware\5banalyze_tax_payout\5d\2eafter_model("ToolCallLimitMiddleware[analyze_tax_payout].after_model")
	ToolCallLimitMiddleware\5banalyze_product\5d\2eafter_model("ToolCallLimitMiddleware[analyze_product].after_model")
	__end__([<p>__end__</p>]):::last
	SupervisorModelCallLimit\2eafter_model -.-> SupervisorModelCallLimit\2ebefore_model;
	SupervisorModelCallLimit\2eafter_model -.-> __end__;
	SupervisorModelCallLimit\2eafter_model -.-> tools;
	SupervisorModelCallLimit\2ebefore_model -.-> __end__;
	SupervisorModelCallLimit\2ebefore_model -.-> model;
	ToolCallLimitMiddleware\5banalyze_policy\5d\2eafter_model -.-> SupervisorModelCallLimit\2eafter_model;
	ToolCallLimitMiddleware\5banalyze_policy\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5banalyze_product\5d\2eafter_model -.-> ToolCallLimitMiddleware\5banalyze_tax_payout\5d\2eafter_model;
	ToolCallLimitMiddleware\5banalyze_product\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5banalyze_tax_payout\5d\2eafter_model -.-> ToolCallLimitMiddleware\5banalyze_policy\5d\2eafter_model;
	ToolCallLimitMiddleware\5banalyze_tax_payout\5d\2eafter_model -.-> __end__;
	__start__ --> SupervisorModelCallLimit\2ebefore_model;
	model --> ToolCallLimitMiddleware\5banalyze_product\5d\2eafter_model;
	tools -.-> SupervisorModelCallLimit\2ebefore_model;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

</details>

## Policy Domain Agent 컴파일 그래프

![Policy Domain Agent 컴파일 그래프](generated/policy.png)

<details>
<summary>Mermaid 원본 보기</summary>

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	model("model")
	tools("tools")
	CompleteDomainResult\2ebefore_model("CompleteDomainResult.before_model")
	RequireDomainTool\2eafter_model("RequireDomainTool.after_model")
	SingleDomainSubmitPerModelCall\2eafter_model("SingleDomainSubmitPerModelCall.after_model")
	DomainModelCallLimit\2ebefore_model("DomainModelCallLimit.before_model")
	DomainModelCallLimit\2eafter_model("DomainModelCallLimit.after_model")
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model("ToolCallLimitMiddleware[search_documents].after_model")
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model("ToolCallLimitMiddleware[submit_domain_result].after_model")
	__end__([<p>__end__</p>]):::last
	CompleteDomainResult\2ebefore_model -.-> DomainModelCallLimit\2ebefore_model;
	CompleteDomainResult\2ebefore_model -.-> __end__;
	DomainModelCallLimit\2eafter_model --> SingleDomainSubmitPerModelCall\2eafter_model;
	DomainModelCallLimit\2ebefore_model -.-> __end__;
	DomainModelCallLimit\2ebefore_model -.-> model;
	RequireDomainTool\2eafter_model -.-> CompleteDomainResult\2ebefore_model;
	RequireDomainTool\2eafter_model -.-> __end__;
	RequireDomainTool\2eafter_model -.-> tools;
	SingleDomainSubmitPerModelCall\2eafter_model --> RequireDomainTool\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> DomainModelCallLimit\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> __end__;
	__start__ --> CompleteDomainResult\2ebefore_model;
	model --> ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model;
	tools -.-> CompleteDomainResult\2ebefore_model;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

</details>

## Tax/Payout Domain Agent 컴파일 그래프

![Tax/Payout Domain Agent 컴파일 그래프](generated/tax-payout.png)

<details>
<summary>Mermaid 원본 보기</summary>

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	model("model")
	tools("tools")
	CompleteDomainResult\2ebefore_model("CompleteDomainResult.before_model")
	RequireDomainTool\2eafter_model("RequireDomainTool.after_model")
	SingleDomainSubmitPerModelCall\2eafter_model("SingleDomainSubmitPerModelCall.after_model")
	DomainModelCallLimit\2ebefore_model("DomainModelCallLimit.before_model")
	DomainModelCallLimit\2eafter_model("DomainModelCallLimit.after_model")
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model("ToolCallLimitMiddleware[search_documents].after_model")
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model("ToolCallLimitMiddleware[submit_domain_result].after_model")
	__end__([<p>__end__</p>]):::last
	CompleteDomainResult\2ebefore_model -.-> DomainModelCallLimit\2ebefore_model;
	CompleteDomainResult\2ebefore_model -.-> __end__;
	DomainModelCallLimit\2eafter_model --> SingleDomainSubmitPerModelCall\2eafter_model;
	DomainModelCallLimit\2ebefore_model -.-> __end__;
	DomainModelCallLimit\2ebefore_model -.-> model;
	RequireDomainTool\2eafter_model -.-> CompleteDomainResult\2ebefore_model;
	RequireDomainTool\2eafter_model -.-> __end__;
	RequireDomainTool\2eafter_model -.-> tools;
	SingleDomainSubmitPerModelCall\2eafter_model --> RequireDomainTool\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> DomainModelCallLimit\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> __end__;
	__start__ --> CompleteDomainResult\2ebefore_model;
	model --> ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model;
	tools -.-> CompleteDomainResult\2ebefore_model;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

</details>

## Product Domain Agent 컴파일 그래프

![Product Domain Agent 컴파일 그래프](generated/product.png)

<details>
<summary>Mermaid 원본 보기</summary>

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	model("model")
	tools("tools")
	CompleteDomainResult\2ebefore_model("CompleteDomainResult.before_model")
	RequireDomainTool\2eafter_model("RequireDomainTool.after_model")
	SingleDomainSubmitPerModelCall\2eafter_model("SingleDomainSubmitPerModelCall.after_model")
	DomainModelCallLimit\2ebefore_model("DomainModelCallLimit.before_model")
	DomainModelCallLimit\2eafter_model("DomainModelCallLimit.after_model")
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model("ToolCallLimitMiddleware[search_documents].after_model")
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model("ToolCallLimitMiddleware[submit_domain_result].after_model")
	__end__([<p>__end__</p>]):::last
	CompleteDomainResult\2ebefore_model -.-> DomainModelCallLimit\2ebefore_model;
	CompleteDomainResult\2ebefore_model -.-> __end__;
	DomainModelCallLimit\2eafter_model --> SingleDomainSubmitPerModelCall\2eafter_model;
	DomainModelCallLimit\2ebefore_model -.-> __end__;
	DomainModelCallLimit\2ebefore_model -.-> model;
	RequireDomainTool\2eafter_model -.-> CompleteDomainResult\2ebefore_model;
	RequireDomainTool\2eafter_model -.-> __end__;
	RequireDomainTool\2eafter_model -.-> tools;
	SingleDomainSubmitPerModelCall\2eafter_model --> RequireDomainTool\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> DomainModelCallLimit\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> __end__;
	__start__ --> CompleteDomainResult\2ebefore_model;
	model --> ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model;
	tools -.-> CompleteDomainResult\2ebefore_model;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

</details>
