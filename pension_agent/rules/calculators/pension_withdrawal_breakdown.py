"""연금계좌 인출 순서 배분과 재원·수령구분별 세액 합성 규칙."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Annotated, Any, Self, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pension_agent.rules.calculators.deferred_retirement_withdrawal_tax import (
    DeferredRetirementWithdrawalTaxInput,
    calculate_deferred_retirement_withdrawal_tax,
)
from pension_agent.rules.calculators.non_pension_withdrawal_tax import (
    NonPensionWithdrawalTaxInput,
    calculate_non_pension_withdrawal_tax,
)
from pension_agent.rules.calculators.pension_income_tax import (
    PensionIncomeTaxInput,
    calculate_pension_income_tax,
)
from pension_agent.rules.models import CalculationOutput, CalculationScalar, CalculatorDefinition

_Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
_Age = Annotated[int, Field(ge=0)]
_ReceiptYear = Annotated[int, Field(ge=1)]
_TAX_FREE_WARNING = "비과세 재원 인출액도 연금수령한도를 소진합니다."
_ANNUAL_OPTION_WARNING = (
    "연간 전체금액의 16.5% 분리과세 선택세액은 현재 인출 세액 합계와 다른 단위입니다."
)


@dataclass(frozen=True, slots=True)
class WithdrawalAllocation:
    """인출 순서에 따라 재원별로 배분된 금액."""

    tax_free: Decimal
    deferred_retirement: Decimal
    credited_and_earnings: Decimal


def allocate_pension_withdrawal(
    requested_withdrawal_krw: Decimal,
    tax_free_source_balance_krw: Decimal,
    deferred_retirement_source_balance_krw: Decimal,
    credited_and_earnings_source_balance_krw: Decimal,
) -> WithdrawalAllocation:
    """비과세·이연퇴직소득·세액공제 원금과 운용수익 순서로 인출액을 배분한다."""

    total_balance = (
        tax_free_source_balance_krw
        + deferred_retirement_source_balance_krw
        + credited_and_earnings_source_balance_krw
    )
    if requested_withdrawal_krw > total_balance:
        raise ValueError("요청 인출액이 전체 재원 잔액을 초과합니다.")

    remaining = requested_withdrawal_krw
    tax_free = min(remaining, tax_free_source_balance_krw)
    remaining -= tax_free
    deferred = min(remaining, deferred_retirement_source_balance_krw)
    remaining -= deferred
    credited = min(remaining, credited_and_earnings_source_balance_krw)
    return WithdrawalAllocation(tax_free, deferred, credited)


class PensionWithdrawalAllocationInput(BaseModel):
    """인출 요청액과 세 재원의 현재 잔액."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_withdrawal_krw: _Money
    tax_free_source_balance_krw: _Money
    deferred_retirement_source_balance_krw: _Money
    credited_and_earnings_source_balance_krw: _Money

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("명시적인 null 입력은 허용하지 않습니다.")
        return value

    @model_validator(mode="after")
    def validate_available_balance(self) -> Self:
        allocate_pension_withdrawal(
            self.requested_withdrawal_krw,
            self.tax_free_source_balance_krw,
            self.deferred_retirement_source_balance_krw,
            self.credited_and_earnings_source_balance_krw,
        )
        return self


def calculate_pension_withdrawal_allocation(
    value: PensionWithdrawalAllocationInput,
) -> CalculationOutput:
    """인출액과 인출 후 재원별 잔액을 반환한다."""

    allocation = allocate_pension_withdrawal(
        value.requested_withdrawal_krw,
        value.tax_free_source_balance_krw,
        value.deferred_retirement_source_balance_krw,
        value.credited_and_earnings_source_balance_krw,
    )
    outputs: dict[str, CalculationScalar] = {
        "tax_free_withdrawal_krw": allocation.tax_free,
        "deferred_retirement_withdrawal_krw": allocation.deferred_retirement,
        "credited_and_earnings_withdrawal_krw": allocation.credited_and_earnings,
        "tax_free_remaining_balance_krw": (value.tax_free_source_balance_krw - allocation.tax_free),
        "deferred_retirement_remaining_balance_krw": (
            value.deferred_retirement_source_balance_krw - allocation.deferred_retirement
        ),
        "credited_and_earnings_remaining_balance_krw": (
            value.credited_and_earnings_source_balance_krw - allocation.credited_and_earnings
        ),
    }
    return CalculationOutput(
        outputs=outputs,
        units={key: "KRW" for key in outputs},
    )


@dataclass(frozen=True, slots=True)
class TreatmentAllocation:
    """세 재원과 pension/non-pension 구간의 교집합 금액."""

    tax_free_pension: Decimal
    tax_free_non_pension: Decimal
    deferred_retirement_pension: Decimal
    deferred_retirement_non_pension: Decimal
    credited_and_earnings_pension: Decimal
    credited_and_earnings_non_pension: Decimal


def _interval_overlap(start: Decimal, end: Decimal, other_end: Decimal) -> Decimal:
    return max(min(end, other_end) - start, Decimal(0))


def _allocate_treatments(
    allocation: WithdrawalAllocation,
    pension_treated_withdrawal_krw: Decimal,
) -> TreatmentAllocation:
    source_amounts = (
        allocation.tax_free,
        allocation.deferred_retirement,
        allocation.credited_and_earnings,
    )
    pension_parts: list[Decimal] = []
    non_pension_parts: list[Decimal] = []
    start = Decimal(0)
    for amount in source_amounts:
        end = start + amount
        pension_part = _interval_overlap(start, end, pension_treated_withdrawal_krw)
        pension_parts.append(pension_part)
        non_pension_parts.append(amount - pension_part)
        start = end
    return TreatmentAllocation(
        pension_parts[0],
        non_pension_parts[0],
        pension_parts[1],
        non_pension_parts[1],
        pension_parts[2],
        non_pension_parts[2],
    )


class PensionWithdrawalTaxBreakdownInput(PensionWithdrawalAllocationInput):
    """재원 순서와 수령구분별 과세에 필요한 확정 입력."""

    pension_treated_withdrawal_krw: _Money
    non_pension_treated_withdrawal_krw: _Money
    actual_pension_receipt_year: _ReceiptYear | None = None
    recipient_age: _Age | None = None
    is_lifetime_annuity: bool | None = None
    annual_private_pension_taxable_income_krw: _Money | None = None
    pension_treated_allocated_deferred_retirement_tax_krw: _Money | None = None
    non_pension_treated_allocated_deferred_retirement_tax_krw: _Money | None = None

    @model_validator(mode="after")
    def validate_tax_paths(self) -> Self:
        if (
            self.pension_treated_withdrawal_krw + self.non_pension_treated_withdrawal_krw
            != self.requested_withdrawal_krw
        ):
            raise ValueError("pension과 non-pension 처리 금액 합계가 요청 인출액과 다릅니다.")

        allocation = allocate_pension_withdrawal(
            self.requested_withdrawal_krw,
            self.tax_free_source_balance_krw,
            self.deferred_retirement_source_balance_krw,
            self.credited_and_earnings_source_balance_krw,
        )
        paths = _allocate_treatments(allocation, self.pension_treated_withdrawal_krw)
        self._validate_deferred_pension_path(paths.deferred_retirement_pension)
        self._validate_deferred_non_pension_path(paths.deferred_retirement_non_pension)
        self._validate_credited_pension_path(paths.credited_and_earnings_pension)
        return self

    def _validate_deferred_pension_path(self, amount: Decimal) -> None:
        if amount > 0:
            if self.actual_pension_receipt_year is None:
                raise ValueError("연금 처리 이연퇴직소득에는 실제수령연차가 필요합니다.")
            if self.pension_treated_allocated_deferred_retirement_tax_krw is None:
                raise ValueError("연금 처리 이연퇴직소득에는 배분세액이 필요합니다.")
            DeferredRetirementWithdrawalTaxInput(
                receipt_type="pension",
                actual_pension_receipt_year=self.actual_pension_receipt_year,
                allocated_deferred_retirement_tax_krw=(
                    self.pension_treated_allocated_deferred_retirement_tax_krw
                ),
            )
        elif self.actual_pension_receipt_year is not None or (
            self.pension_treated_allocated_deferred_retirement_tax_krw is not None
        ):
            raise ValueError("연금 처리 이연퇴직소득 경로가 없으면 관련 입력을 생략해야 합니다.")

    def _validate_deferred_non_pension_path(self, amount: Decimal) -> None:
        if amount > 0:
            if self.non_pension_treated_allocated_deferred_retirement_tax_krw is None:
                raise ValueError("연금외 처리 이연퇴직소득에는 배분세액이 필요합니다.")
            DeferredRetirementWithdrawalTaxInput(
                receipt_type="non_pension",
                allocated_deferred_retirement_tax_krw=(
                    self.non_pension_treated_allocated_deferred_retirement_tax_krw
                ),
            )
        elif self.non_pension_treated_allocated_deferred_retirement_tax_krw is not None:
            raise ValueError("연금외 처리 이연퇴직소득 경로가 없으면 배분세액을 생략해야 합니다.")

    def _validate_credited_pension_path(self, amount: Decimal) -> None:
        optional_values = (
            self.recipient_age,
            self.is_lifetime_annuity,
            self.annual_private_pension_taxable_income_krw,
        )
        if amount > 0:
            if self.recipient_age is None or self.is_lifetime_annuity is None:
                raise ValueError(
                    "연금 처리 세액공제 원금·운용수익에는 나이와 종신 여부가 필요합니다."
                )
            _ordinary_pension_income_input(
                amount,
                self.recipient_age,
                self.is_lifetime_annuity,
                self.annual_private_pension_taxable_income_krw,
            )
        elif any(value is not None for value in optional_values):
            raise ValueError(
                "연금 처리 세액공제 원금·운용수익 경로가 없으면 관련 입력을 생략해야 합니다."
            )


def _deduplicated_warnings(warnings: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(warnings))


def _ordinary_pension_income_input(
    amount: Decimal,
    recipient_age: int,
    is_lifetime_annuity: bool,
    annual_income: Decimal | None,
) -> PensionIncomeTaxInput:
    inputs: dict[str, Any] = {
        "pension_treatment": "ordinary",
        "recipient_age": recipient_age,
        "target_taxable_amount_krw": amount,
        "is_lifetime_annuity": is_lifetime_annuity,
    }
    if annual_income is not None:
        inputs["annual_private_pension_taxable_income_krw"] = annual_income
    return PensionIncomeTaxInput.model_validate(inputs)


def _decimal_output(output: CalculationOutput, key: str) -> Decimal:
    return cast(Decimal, output.outputs[key])


def calculate_pension_withdrawal_tax_breakdown(
    value: PensionWithdrawalTaxBreakdownInput,
) -> CalculationOutput:
    """재원·수령구분별 인출액, 세액과 세후액을 기존 세금 순수 함수로 합성한다."""

    allocation = allocate_pension_withdrawal(
        value.requested_withdrawal_krw,
        value.tax_free_source_balance_krw,
        value.deferred_retirement_source_balance_krw,
        value.credited_and_earnings_source_balance_krw,
    )
    paths = _allocate_treatments(allocation, value.pension_treated_withdrawal_krw)
    withdrawals = {
        "tax_free_pension": paths.tax_free_pension,
        "tax_free_non_pension": paths.tax_free_non_pension,
        "deferred_retirement_pension": paths.deferred_retirement_pension,
        "deferred_retirement_non_pension": paths.deferred_retirement_non_pension,
        "credited_and_earnings_pension": paths.credited_and_earnings_pension,
        "credited_and_earnings_non_pension": paths.credited_and_earnings_non_pension,
    }
    taxes: dict[str, Decimal | None] = {
        "tax_free_pension": Decimal(0),
        "tax_free_non_pension": Decimal(0),
    }
    warnings: list[str] = []
    annual_option_tax: Decimal | None = None

    deferred_pension = paths.deferred_retirement_pension
    if deferred_pension > 0:
        if value.actual_pension_receipt_year is None or (
            value.pension_treated_allocated_deferred_retirement_tax_krw is None
        ):
            raise ValueError("연금 처리 이연퇴직소득 필수 입력이 없습니다.")
        result = calculate_deferred_retirement_withdrawal_tax(
            DeferredRetirementWithdrawalTaxInput(
                receipt_type="pension",
                actual_pension_receipt_year=value.actual_pension_receipt_year,
                allocated_deferred_retirement_tax_krw=(
                    value.pension_treated_allocated_deferred_retirement_tax_krw
                ),
            )
        )
        taxes["deferred_retirement_pension"] = _decimal_output(result, "tax_payable_krw")
        warnings.extend(result.warnings)
    else:
        taxes["deferred_retirement_pension"] = Decimal(0)

    deferred_non_pension = paths.deferred_retirement_non_pension
    if deferred_non_pension > 0:
        if value.non_pension_treated_allocated_deferred_retirement_tax_krw is None:
            raise ValueError("연금외 처리 이연퇴직소득 배분세액이 없습니다.")
        result = calculate_deferred_retirement_withdrawal_tax(
            DeferredRetirementWithdrawalTaxInput(
                receipt_type="non_pension",
                allocated_deferred_retirement_tax_krw=(
                    value.non_pension_treated_allocated_deferred_retirement_tax_krw
                ),
            )
        )
        taxes["deferred_retirement_non_pension"] = _decimal_output(result, "tax_payable_krw")
        warnings.extend(result.warnings)
    else:
        taxes["deferred_retirement_non_pension"] = Decimal(0)

    credited_pension = paths.credited_and_earnings_pension
    if credited_pension > 0:
        if value.recipient_age is None or value.is_lifetime_annuity is None:
            raise ValueError("연금 처리 세액공제 원금·운용수익 필수 입력이 없습니다.")
        result = calculate_pension_income_tax(
            _ordinary_pension_income_input(
                credited_pension,
                value.recipient_age,
                value.is_lifetime_annuity,
                value.annual_private_pension_taxable_income_krw,
            )
        )
        tax = result.outputs.get("tax_krw")
        taxes["credited_and_earnings_pension"] = tax if isinstance(tax, Decimal) else None
        separate_tax = result.outputs.get("separate_tax_option_tax_krw")
        if isinstance(separate_tax, Decimal):
            annual_option_tax = separate_tax
            warnings.append(_ANNUAL_OPTION_WARNING)
        warnings.extend(result.warnings)
    else:
        taxes["credited_and_earnings_pension"] = Decimal(0)

    credited_non_pension = paths.credited_and_earnings_non_pension
    if credited_non_pension > 0:
        result = calculate_non_pension_withdrawal_tax(
            NonPensionWithdrawalTaxInput(taxable_amount_krw=credited_non_pension)
        )
        taxes["credited_and_earnings_non_pension"] = _decimal_output(result, "tax_krw")
        warnings.extend(result.warnings)
    else:
        taxes["credited_and_earnings_non_pension"] = Decimal(0)

    outputs: dict[str, CalculationScalar] = {}
    current_tax: Decimal | None = Decimal(0)
    current_after_tax: Decimal | None = Decimal(0)
    with localcontext() as context:
        context.prec = 28
        for path, withdrawal in withdrawals.items():
            tax = taxes[path]
            outputs[f"{path}_withdrawal_krw"] = withdrawal
            outputs[f"{path}_tax_krw"] = tax
            if tax is None:
                outputs[f"{path}_after_tax_krw"] = None
                current_tax = None
                current_after_tax = None
            else:
                after_tax = withdrawal - tax
                outputs[f"{path}_after_tax_krw"] = after_tax
                if current_tax is not None and current_after_tax is not None:
                    current_tax += tax
                    current_after_tax += after_tax

    outputs["current_withdrawal_tax_krw"] = current_tax
    outputs["current_withdrawal_after_tax_krw"] = current_after_tax
    if annual_option_tax is not None:
        outputs["annual_private_pension_separate_tax_option_tax_krw"] = annual_option_tax
    if allocation.tax_free > 0:
        warnings.append(_TAX_FREE_WARNING)
    return CalculationOutput(
        outputs=outputs,
        units={key: "KRW" for key in outputs},
        warnings=_deduplicated_warnings(warnings),
    )


PENSION_WITHDRAWAL_ALLOCATION = CalculatorDefinition(
    input_model=PensionWithdrawalAllocationInput,
    calculate=calculate_pension_withdrawal_allocation,
)

PENSION_WITHDRAWAL_TAX_BREAKDOWN = CalculatorDefinition(
    input_model=PensionWithdrawalTaxBreakdownInput,
    calculate=calculate_pension_withdrawal_tax_breakdown,
)
