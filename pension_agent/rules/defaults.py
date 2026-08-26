"""출처 검증을 마친 초기 계산기 Registry 조립."""

from pension_agent.rules.calculators import INITIAL_CALCULATORS
from pension_agent.rules.registry import CalculationRegistry
from pension_agent.rules.service import CalculationService


def build_default_calculation_registry() -> CalculationRegistry:
    """패키지에 포함된 active 초기 계산기를 새 Registry에 등록한다."""

    registry = CalculationRegistry()
    for definition in INITIAL_CALCULATORS:
        registry.register(definition)
    return registry


def create_default_calculation_service() -> CalculationService:
    """Agent에 연결되지 않은 기본 Calculation Service를 만든다."""

    return CalculationService(build_default_calculation_registry())
