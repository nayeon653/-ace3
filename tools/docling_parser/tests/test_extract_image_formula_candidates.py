from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image


def _load_script():
    script_path = Path(__file__).parents[1] / "scripts" / "extract_image_formula_candidates.py"
    spec = importlib.util.spec_from_file_location("extract_image_formula_candidates", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_margin_decoration_gate_only_excludes_small_margin_picture() -> None:
    module = _load_script()
    page = {"width": 595, "height": 842}

    assert module._is_margin_decoration({"l": 480, "r": 555, "b": 20, "t": 50}, page)
    assert not module._is_margin_decoration({"l": 200, "r": 395, "b": 350, "t": 430}, page)
    assert not module._is_margin_decoration({"l": 20, "r": 575, "b": 10, "t": 150}, page)


def test_visual_fingerprint_is_stable_for_same_pixels() -> None:
    module = _load_script()
    first = Image.new("RGB", (200, 100), "white")
    second = first.copy()

    assert module._visual_fingerprint(first) == module._visual_fingerprint(second)


def test_formula_gate_requires_docling_formula_syntax() -> None:
    module = _load_script()

    assert module._formula_is_usable([r"x = \\frac{a}{b}"])
    assert module._formula_is_usable(["MAX(a, b)"])
    assert not module._formula_is_usable(["주식회사 로고"])
