"""업무·제도 Domain Agent 조립."""

from importlib import resources

from langchain_core.language_models import BaseChatModel

from pension_agent.agent.domain_runner import GuardedDomainRunner
from pension_agent.agent.execution import ModelConcurrencyMiddleware
from pension_agent.agent.policy.react import create_policy_react_agent
from pension_agent.agent.search import SearchRunner
from pension_agent.config import DEFAULT_DOMAIN_AGENT_CONFIG, DomainAgentConfig

POLICY_TOOL_NAME = "analyze_policy"
POLICY_TOOL_DESCRIPTION = (
    "연금·ISA 계좌와 제도의 가입·납입·이전·해지·수령 신청, 계좌 상태와 거래 가능 "
    "범위, 업무 서비스·메뉴·증명서·오류 및 계좌 수준 수수료를 판단한다. 세금 계산과 "
    "개별 펀드 특성은 다루지 않는다."
)


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
    search_service: SearchRunner,
    config: DomainAgentConfig = DEFAULT_DOMAIN_AGENT_CONFIG,
    model_concurrency: ModelConcurrencyMiddleware | None = None,
) -> GuardedDomainRunner:
    """단일 Search Service Tool만 사용하는 업무·제도 Agent를 만든다."""

    implementation = create_policy_react_agent(
        model=model,
        search_service=search_service,
        system_prompt=load_policy_agent_prompt(),
        config=config,
        model_concurrency=model_concurrency,
    )
    return GuardedDomainRunner(
        domain="policy",
        implementation=implementation,
        config=config,
    )
