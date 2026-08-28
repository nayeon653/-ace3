"""연금계좌 납입액의 세액공제 대상액과 세액 계산 규칙."""

from decimal import Decimal, localcontext
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from pension_agent.rules.models import (
    CalculationOutput,
    CalculationScalar,
    CalculatorDefinition,
)

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_IsaPriorUsed = Annotated[
    Decimal,
    Field(ge=0, le=3_000_000, allow_inf_nan=False),
]
IncomeBasis = Literal["salary", "comprehensive_income"]

_PENSION_SAVINGS_LIMIT = Decimal(6000000)
_COMBINED_REGULAR_LIMIT = Decimal(9000000)
_ISA_EXTRA_LIMIT = Decimal(3000000)

_LOWER_SALARY_THRESHOLD = Decimal(55000000)
_LOWER_COMPREHENSIVE_INCOME_THRESHOLD = Decimal(45000000)

_LOWER_CREDIT_RATE = Decimal("0.165")
_OTHER_CREDIT_RATE = Decimal("0.132")


class PensionTaxCreditInput(BaseModel):
    """연금계좌 세액공제 계산에 필요한 납입액과 소득정보."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pension_savings_net_contribution_krw: _Money
    retirement_pension_net_contribution_krw: _Money

    pension_savings_isa_transfer_krw: _Money | None = None
    retirement_pension_isa_transfer_krw: _Money | None = None
    prior_same_maturity_isa_extra_eligible_contribution_used_krw: _IsaPriorUsed | None = None

    income_basis: IncomeBasis | None = None
    income_amount_krw: _Money | None = None
    remaining_tax_before_pension_credit_krw: _Money | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        """생략은 허용하지만 명시적으로 전달한 null은 거부한다."""

        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value

    @model_validator(mode="after")
    def validate_related_fields(self) -> Self:
        """ISA 전환액과 소득 관련 필드의 상호 조건을 검증한다."""

        savings_isa_transfer = (
            self.pension_savings_isa_transfer_krw
            if self.pension_savings_isa_transfer_krw is not None
            else Decimal(0)
        )
        retirement_isa_transfer = (
            self.retirement_pension_isa_transfer_krw
            if self.retirement_pension_isa_transfer_krw is not None
            else Decimal(0)
        )
        total_isa_transfer = savings_isa_transfer + retirement_isa_transfer

        if savings_isa_transfer > self.pension_savings_net_contribution_krw:
            raise ValueError("연금저축 ISA 전환액은 연금저축 순납입액을 초과할 수 없습니다.")

        if retirement_isa_transfer > self.retirement_pension_net_contribution_krw:
            raise ValueError("퇴직연금 ISA 전환액은 퇴직연금 순납입액을 초과할 수 없습니다.")

        prior_isa_used = self.prior_same_maturity_isa_extra_eligible_contribution_used_krw

        if total_isa_transfer > 0 and prior_isa_used is None:
            raise ValueError(
                "ISA 전환액이 있으면 같은 만기자금의 기존 추가 공제대상액이 필요합니다."
            )

        if total_isa_transfer == 0 and prior_isa_used is not None:
            raise ValueError("ISA 전환액이 없으면 기존 추가 공제대상액을 입력할 수 없습니다.")

        has_income_basis = self.income_basis is not None
        has_income_amount = self.income_amount_krw is not None

        if has_income_basis != has_income_amount:
            raise ValueError("소득 기준과 소득금액은 함께 입력하거나 함께 생략해야 합니다.")

        if self.remaining_tax_before_pension_credit_krw is not None and not has_income_basis:
            raise ValueError("잔여 세액을 입력하려면 소득 기준과 소득금액이 필요합니다.")

        return self


def calculate_pension_tax_credit(
    value: PensionTaxCreditInput,
) -> CalculationOutput:
    """일반 납입과 ISA 전환 납입의 세액공제 대상액과 세액을 계산한다."""

    savings_isa_transfer = (
        value.pension_savings_isa_transfer_krw
        if value.pension_savings_isa_transfer_krw is not None
        else Decimal(0)
    )
    retirement_isa_transfer = (
        value.retirement_pension_isa_transfer_krw
        if value.retirement_pension_isa_transfer_krw is not None
        else Decimal(0)
    )
    prior_isa_used = (
        value.prior_same_maturity_isa_extra_eligible_contribution_used_krw
        if value.prior_same_maturity_isa_extra_eligible_contribution_used_krw is not None
        else Decimal(0)
    )

    with localcontext() as context:
        context.prec = 28

        regular_eligible = min(
            _COMBINED_REGULAR_LIMIT,
            min(
                value.pension_savings_net_contribution_krw,
                _PENSION_SAVINGS_LIMIT,
            )
            + value.retirement_pension_net_contribution_krw,
        )

        isa_transfer = savings_isa_transfer + retirement_isa_transfer
        isa_remaining_cap = max(
            _ISA_EXTRA_LIMIT - prior_isa_used,
            Decimal(0),
        )
        isa_extra_limit = min(
            isa_transfer * Decimal("0.10"),
            isa_remaining_cap,
        )

        total_net_contribution = (
            value.pension_savings_net_contribution_krw
            + value.retirement_pension_net_contribution_krw
        )
        eligible_contribution = min(
            total_net_contribution,
            regular_eligible + isa_extra_limit,
        )
        realized_isa_extra = max(
            eligible_contribution - regular_eligible,
            Decimal(0),
        )

        outputs: dict[str, CalculationScalar] = {
            "regular_eligible_contribution_krw": regular_eligible,
            "isa_extra_remaining_cap_krw": isa_remaining_cap,
            "isa_extra_limit_krw": isa_extra_limit,
            "isa_extra_eligible_contribution_krw": realized_isa_extra,
            "eligible_contribution_krw": eligible_contribution,
        }
        units = {key: "KRW" for key in outputs}

        income_amount = value.income_amount_krw

        if value.income_basis is None:
            outputs.update(
                {
                    "lower_income_rate_percent": Decimal("16.5"),
                    "lower_income_theoretical_credit_krw": (
                        eligible_contribution * _LOWER_CREDIT_RATE
                    ),
                    "other_income_rate_percent": Decimal("13.2"),
                    "other_income_theoretical_credit_krw": (
                        eligible_contribution * _OTHER_CREDIT_RATE
                    ),
                }
            )
            units.update(
                {
                    "lower_income_rate_percent": "%",
                    "lower_income_theoretical_credit_krw": "KRW",
                    "other_income_rate_percent": "%",
                    "other_income_theoretical_credit_krw": "KRW",
                }
            )
        else:
            if income_amount is None:
                raise ValueError("소득 기준에 대응하는 소득금액이 없습니다.")

            threshold = (
                _LOWER_SALARY_THRESHOLD
                if value.income_basis == "salary"
                else _LOWER_COMPREHENSIVE_INCOME_THRESHOLD
            )
            credit_rate = _LOWER_CREDIT_RATE if income_amount <= threshold else _OTHER_CREDIT_RATE
            theoretical_credit = eligible_contribution * credit_rate

            outputs.update(
                {
                    "credit_rate_percent": credit_rate * Decimal(100),
                    "theoretical_credit_krw": theoretical_credit,
                }
            )
            units.update(
                {
                    "credit_rate_percent": "%",
                    "theoretical_credit_krw": "KRW",
                }
            )

            remaining_tax = value.remaining_tax_before_pension_credit_krw
            if remaining_tax is not None:
                outputs["usable_credit_krw"] = min(
                    theoretical_credit,
                    remaining_tax,
                )
                units["usable_credit_krw"] = "KRW"

    return CalculationOutput(
        outputs=outputs,
        units=units,
        warnings=(
            "출처에는 원 단위 세액의 반올림·절사 규칙이 명시되지 않았습니다.",
            "계산 결과는 원천징수세액과 기납부세액을 반영한 실제 환급액이 아닙니다.",
        ),
    )


PENSION_TAX_CREDIT = CalculatorDefinition(
    input_model=PensionTaxCreditInput,
    calculate=calculate_pension_tax_credit,
)
