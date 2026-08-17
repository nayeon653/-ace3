"""Search Agent의 현재 기본 동작 프로필."""

from pension_agent.config.search_agent import SearchAgentConfig
from pension_agent.core import SearchMode

DEFAULT_SEARCH_AGENT_CONFIG = SearchAgentConfig(
    max_model_calls=4,
    max_tool_calls=3,
    default_search_mode=SearchMode.HYBRID,
    default_result_limit=10,
    default_neighbor_before=1,
    default_neighbor_after=1,
)
