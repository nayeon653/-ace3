"""연금계좌 평가액과 연금수령연차에 따른 연금수령한도 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pension_agent.rules.models import CalculationOutput, CalculatorDefinition

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class PensionWithdrawalLimitInput(BaseModel):
    """연금수령한도의 평가액과 수령연차."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account_valuation_krw: _Money | None = None
    pension_year: int = Field(ge=1)

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        """선택 필드 생략은 허용하되 명시적인 null은 거부한다."""

        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value

    @model_validator(mode="after")
    def require_valuation_when_limit_applies(self) -> Self:
        """1~10년차에는 한도 산출을 위한 평가액이 필요하다."""

        if self.pension_year <= 10 and self.account_valuation_krw is None:
            raise ValueError("1~10년차에는 계좌 평가액이 필요합니다.")
        return self


def calculate_pension_withdrawal_limit(
    value: PensionWithdrawalLimitInput,
) -> CalculationOutput:
    """평가액 ÷ (11 - 수령연차) × 120% 공식을 적용한다."""

    if value.pension_year >= 11:
        warnings: tuple[str, ...] = ()
        if value.account_valuation_krw is not None:
            warnings = ("11년차 이상에는 계좌 평가액을 연금수령한도 계산에 사용하지 않습니다.",)
        return CalculationOutput(
            outputs={"withdrawal_limit": None, "limit_applies": False},
            units={"withdrawal_limit": "KRW"},
            warnings=warnings,
        )

    valuation = value.account_valuation_krw
    if valuation is None:
        raise ValueError("계좌 평가액이 없습니다.")
    with localcontext() as context:
        context.prec = 28
        limit = valuation / Decimal(11 - value.pension_year) * Decimal("1.2")
    return CalculationOutput(
        outputs={"withdrawal_limit": limit, "limit_applies": True},
        units={"withdrawal_limit": "KRW"},
        warnings=("출처에는 최종 지급 단위의 반올림·절사 규칙이 명시되지 않았습니다.",),
    )


PENSION_WITHDRAWAL_LIMIT = CalculatorDefinition(
    input_model=PensionWithdrawalLimitInput,
    calculate=calculate_pension_withdrawal_limit,
)
