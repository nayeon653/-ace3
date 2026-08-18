"""업무·제도 Domain Agent 조립."""

from importlib import resources

from langchain_core.language_models import BaseChatModel

from pension_agent.agent.contracts import Permission
from pension_agent.agent.domain_agent import DomainAgent, create_domain_agent
from pension_agent.agent.search import SearchAgentAdapter
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig

POLICY_TOOL_NAME = "analyze_policy"
POLICY_TOOL_DESCRIPTION = "연금 가입, 이전, 해지, 수령 절차와 제도상 가능 여부를 판단한다."


def load_policy_agent_prompt() -> str:
    """패키지 리소스에서 업무·제도 프롬프트를 읽는다."""

    return (
        resources.files("pension_agent.prompts")
        .joinpath("domain", "policy-agent.md")
        .read_text(encoding="utf-8")
    )


def create_policy_agent(
    *,
    model: BaseChatModel,
    search_adapter: SearchAgentAdapter,
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG,
) -> DomainAgent:
    """Search Agent Tool만 사용하는 업무·제도 Agent를 만든다."""

    return create_domain_agent(
        domain="policy",
        permission=Permission.POLICY,
        model=model,
        search_adapter=search_adapter,
        system_prompt=load_policy_agent_prompt(),
        config=config,
    )
