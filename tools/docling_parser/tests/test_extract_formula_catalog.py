from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script():
    script_path = Path(__file__).parents[1] / "scripts" / "extract_formula_catalog.py"
    spec = importlib.util.spec_from_file_location("extract_formula_catalog", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_explicit_formula_keeps_multiplication_but_rejects_footnote_star() -> None:
    module = _load_script()

    formula_kind, _ = module._signals(
        module._normalize("평균임금 30일분×계속근로기간"), label="text"
    )
    footnote_kind, _ = module._signals(
        module._normalize("별도의 퇴직급여제도*를 적용받습니다"), label="text"
    )

    assert formula_kind == "explicit_equation"
    assert footnote_kind is None


def test_formula_label_is_always_retained() -> None:
    module = _load_script()

    kind, _ = module._signals(r"x = \\frac{a}{b}", label="formula")

    assert kind == "docling_formula"
