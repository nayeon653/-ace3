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
        supervisor["HCX-007 model"] <--> domain_tools["Domain Agent tools"]
    end

    domain_tools -->|analyze_policy| domain_policy
    domain_tools -->|analyze_tax_payout| domain_tax_payout
    domain_tools -->|analyze_product| domain_product

    subgraph domains["Domain Agents · 각각 CompiledStateGraph"]
        domain_policy["Policy Agent<br/>HCX-005"]
        domain_tax_payout["Tax/Payout Agent<br/>HCX-005"]
        domain_product["Product Agent<br/>HCX-007"]
    end

    domain_policy --> domain_tools
    domain_policy --> search_tools
    domain_tax_payout --> domain_tools
    domain_tax_payout --> search_tools
    domain_product --> domain_tools
    domain_product --> search_tools

    subgraph catalog["HCX 카탈로그 Query 계획 · Python 조회"]
        catalog_lookup["lookup_product_codes"] --> catalog_hcx["HCX-005 model"]
        product_catalog["상품 카탈로그"] --> catalog_hcx
        catalog_hcx --> catalog_query["검증된 CatalogQueryPlan"]
        catalog_query --> catalog_execute["Python 정확 조회"]
        product_catalog --> catalog_execute
        catalog_execute --> catalog_result["CatalogResult"]
    end
    domain_product --> catalog_lookup
    catalog_result --> domain_product

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
	CompletePolicyResult\2ebefore_model("CompletePolicyResult.before_model")
	RequirePolicyTool\2eafter_model("RequirePolicyTool.after_model")
	SinglePolicySubmitPerModelCall\2eafter_model("SinglePolicySubmitPerModelCall.after_model")
	PolicyModelCallLimit\2ebefore_model("PolicyModelCallLimit.before_model")
	PolicyModelCallLimit\2eafter_model("PolicyModelCallLimit.after_model")
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model("ToolCallLimitMiddleware[search_documents].after_model")
	ToolCallLimitMiddleware\5bcalculate_dc_medical_withdrawal_threshold\5d\2eafter_model("ToolCallLimitMiddleware[calculate_dc_medical_withdrawal_threshold].after_model")
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model("ToolCallLimitMiddleware[submit_domain_result].after_model")
	EnforcePolicyToolSequence\2eafter_model("EnforcePolicyToolSequence.after_model")
	__end__([<p>__end__</p>]):::last
	CompletePolicyResult\2ebefore_model -.-> PolicyModelCallLimit\2ebefore_model;
	CompletePolicyResult\2ebefore_model -.-> __end__;
	EnforcePolicyToolSequence\2eafter_model --> ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model;
	PolicyModelCallLimit\2eafter_model --> SinglePolicySubmitPerModelCall\2eafter_model;
	PolicyModelCallLimit\2ebefore_model -.-> __end__;
	PolicyModelCallLimit\2ebefore_model -.-> model;
	RequirePolicyTool\2eafter_model -.-> CompletePolicyResult\2ebefore_model;
	RequirePolicyTool\2eafter_model -.-> __end__;
	RequirePolicyTool\2eafter_model -.-> tools;
	SinglePolicySubmitPerModelCall\2eafter_model --> RequirePolicyTool\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_dc_medical_withdrawal_threshold\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_dc_medical_withdrawal_threshold\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> PolicyModelCallLimit\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_dc_medical_withdrawal_threshold\5d\2eafter_model;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> __end__;
	__start__ --> CompletePolicyResult\2ebefore_model;
	model --> EnforcePolicyToolSequence\2eafter_model;
	tools -.-> CompletePolicyResult\2ebefore_model;
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
	CompleteTaxPayoutResult\2ebefore_model("CompleteTaxPayoutResult.before_model")
	RequireTaxPayoutTool\2eafter_model("RequireTaxPayoutTool.after_model")
	SingleTaxPayoutSubmitPerModelCall\2eafter_model("SingleTaxPayoutSubmitPerModelCall.after_model")
	TaxPayoutModelCallLimit\2ebefore_model("TaxPayoutModelCallLimit.before_model")
	TaxPayoutModelCallLimit\2eafter_model("TaxPayoutModelCallLimit.after_model")
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model("ToolCallLimitMiddleware[search_documents].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_limit\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_withdrawal_limit].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_annual_limit_installment\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_annual_limit_installment].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_period_installment\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_period_installment].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_unit_installment\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_unit_installment].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_tax_credit\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_tax_credit].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_income_tax\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_income_tax].after_model")
	ToolCallLimitMiddleware\5bcalculate_non_pension_withdrawal_tax\5d\2eafter_model("ToolCallLimitMiddleware[calculate_non_pension_withdrawal_tax].after_model")
	ToolCallLimitMiddleware\5bcalculate_deferred_retirement_withdrawal_tax\5d\2eafter_model("ToolCallLimitMiddleware[calculate_deferred_retirement_withdrawal_tax].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_allocation\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_withdrawal_allocation].after_model")
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_tax_breakdown\5d\2eafter_model("ToolCallLimitMiddleware[calculate_pension_withdrawal_tax_breakdown].after_model")
	ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_limit\5d\2eafter_model("ToolCallLimitMiddleware[calculate_medical_care_withdrawal_tax_limit].after_model")
	ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_breakdown\5d\2eafter_model("ToolCallLimitMiddleware[calculate_medical_care_withdrawal_tax_breakdown].after_model")
	ToolCallLimitMiddleware\5bcalculate_db_retirement_benefit\5d\2eafter_model("ToolCallLimitMiddleware[calculate_db_retirement_benefit].after_model")
	ToolCallLimitMiddleware\5bcalculate_dc_minimum_employer_contribution\5d\2eafter_model("ToolCallLimitMiddleware[calculate_dc_minimum_employer_contribution].after_model")
	ToolCallLimitMiddleware\5bcalculate_dc_retirement_benefit\5d\2eafter_model("ToolCallLimitMiddleware[calculate_dc_retirement_benefit].after_model")
	ToolCallLimitMiddleware\5bcalculate_db_to_dc_transfer_amount\5d\2eafter_model("ToolCallLimitMiddleware[calculate_db_to_dc_transfer_amount].after_model")
	ToolCallLimitMiddleware\5bcalculate_executive_retirement_income_limit\5d\2eafter_model("ToolCallLimitMiddleware[calculate_executive_retirement_income_limit].after_model")
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model("ToolCallLimitMiddleware[submit_domain_result].after_model")
	EnforceTaxPayoutToolSequence\2eafter_model("EnforceTaxPayoutToolSequence.after_model")
	__end__([<p>__end__</p>]):::last
	CompleteTaxPayoutResult\2ebefore_model -.-> TaxPayoutModelCallLimit\2ebefore_model;
	CompleteTaxPayoutResult\2ebefore_model -.-> __end__;
	EnforceTaxPayoutToolSequence\2eafter_model --> ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model;
	RequireTaxPayoutTool\2eafter_model -.-> CompleteTaxPayoutResult\2ebefore_model;
	RequireTaxPayoutTool\2eafter_model -.-> __end__;
	RequireTaxPayoutTool\2eafter_model -.-> tools;
	SingleTaxPayoutSubmitPerModelCall\2eafter_model --> RequireTaxPayoutTool\2eafter_model;
	TaxPayoutModelCallLimit\2eafter_model --> SingleTaxPayoutSubmitPerModelCall\2eafter_model;
	TaxPayoutModelCallLimit\2ebefore_model -.-> __end__;
	TaxPayoutModelCallLimit\2ebefore_model -.-> model;
	ToolCallLimitMiddleware\5bcalculate_db_retirement_benefit\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_breakdown\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_db_retirement_benefit\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_db_to_dc_transfer_amount\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_dc_retirement_benefit\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_db_to_dc_transfer_amount\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_dc_minimum_employer_contribution\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_db_retirement_benefit\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_dc_minimum_employer_contribution\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_dc_retirement_benefit\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_dc_minimum_employer_contribution\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_dc_retirement_benefit\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_deferred_retirement_withdrawal_tax\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_non_pension_withdrawal_tax\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_deferred_retirement_withdrawal_tax\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_executive_retirement_income_limit\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_db_to_dc_transfer_amount\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_executive_retirement_income_limit\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_breakdown\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_limit\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_breakdown\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_limit\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_tax_breakdown\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_medical_care_withdrawal_tax_limit\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_non_pension_withdrawal_tax\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_income_tax\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_non_pension_withdrawal_tax\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_annual_limit_installment\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_limit\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_annual_limit_installment\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_income_tax\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_tax_credit\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_income_tax\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_period_installment\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_annual_limit_installment\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_period_installment\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_tax_credit\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_unit_installment\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_tax_credit\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_unit_installment\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_period_installment\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_unit_installment\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_allocation\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_deferred_retirement_withdrawal_tax\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_allocation\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_limit\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_limit\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_tax_breakdown\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_allocation\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_pension_withdrawal_tax_breakdown\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> TaxPayoutModelCallLimit\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_executive_retirement_income_limit\5d\2eafter_model;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> __end__;
	__start__ --> CompleteTaxPayoutResult\2ebefore_model;
	model --> EnforceTaxPayoutToolSequence\2eafter_model;
	tools -.-> CompleteTaxPayoutResult\2ebefore_model;
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
	CompleteProductResult\2ebefore_model("CompleteProductResult.before_model")
	RequireProductTool\2eafter_model("RequireProductTool.after_model")
	SingleProductSubmitPerModelCall\2eafter_model("SingleProductSubmitPerModelCall.after_model")
	ProductModelCallLimit\2ebefore_model("ProductModelCallLimit.before_model")
	ProductModelCallLimit\2eafter_model("ProductModelCallLimit.after_model")
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model("ToolCallLimitMiddleware[search_documents].after_model")
	ToolCallLimitMiddleware\5blookup_product_codes\5d\2eafter_model("ToolCallLimitMiddleware[lookup_product_codes].after_model")
	ToolCallLimitMiddleware\5bcalculate_fund_standard_price\5d\2eafter_model("ToolCallLimitMiddleware[calculate_fund_standard_price].after_model")
	ToolCallLimitMiddleware\5bcalculate_fund_var_risk\5d\2eafter_model("ToolCallLimitMiddleware[calculate_fund_var_risk].after_model")
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model("ToolCallLimitMiddleware[submit_domain_result].after_model")
	EnforceProductToolSequence\2eafter_model("EnforceProductToolSequence.after_model")
	__end__([<p>__end__</p>]):::last
	CompleteProductResult\2ebefore_model -.-> ProductModelCallLimit\2ebefore_model;
	CompleteProductResult\2ebefore_model -.-> __end__;
	EnforceProductToolSequence\2eafter_model --> ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model;
	ProductModelCallLimit\2eafter_model --> SingleProductSubmitPerModelCall\2eafter_model;
	ProductModelCallLimit\2ebefore_model -.-> __end__;
	ProductModelCallLimit\2ebefore_model -.-> model;
	RequireProductTool\2eafter_model -.-> CompleteProductResult\2ebefore_model;
	RequireProductTool\2eafter_model -.-> __end__;
	RequireProductTool\2eafter_model -.-> tools;
	SingleProductSubmitPerModelCall\2eafter_model --> RequireProductTool\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_fund_standard_price\5d\2eafter_model -.-> ToolCallLimitMiddleware\5blookup_product_codes\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_fund_standard_price\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bcalculate_fund_var_risk\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_fund_standard_price\5d\2eafter_model;
	ToolCallLimitMiddleware\5bcalculate_fund_var_risk\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5blookup_product_codes\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model;
	ToolCallLimitMiddleware\5blookup_product_codes\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> ProductModelCallLimit\2eafter_model;
	ToolCallLimitMiddleware\5bsearch_documents\5d\2eafter_model -.-> __end__;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> ToolCallLimitMiddleware\5bcalculate_fund_var_risk\5d\2eafter_model;
	ToolCallLimitMiddleware\5bsubmit_domain_result\5d\2eafter_model -.-> __end__;
	__start__ --> CompleteProductResult\2ebefore_model;
	model --> EnforceProductToolSequence\2eafter_model;
	tools -.-> CompleteProductResult\2ebefore_model;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

</details>
