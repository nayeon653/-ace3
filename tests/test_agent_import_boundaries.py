"""Agent 내부 모듈 경계를 정적 import 기준으로 검증한다."""

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1] / "pension_agent"
AGENT_ROOT = PACKAGE_ROOT / "agent"
DOMAIN_PACKAGES = ("policy", "product", "tax_payout")


def _python_files(directory: Path) -> Iterable[Path]:
    return directory.rglob("*.py")


def _absolute_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def _assert_no_imports(directory: Path, forbidden_prefixes: tuple[str, ...]) -> None:
    violations: list[str] = []
    for path in _python_files(directory):
        for imported in _absolute_imports(path):
            if imported.startswith(forbidden_prefixes):
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} -> {imported}")
    assert violations == []


def test_contracts_do_not_depend_on_agent_implementations() -> None:
    _assert_no_imports(
        AGENT_ROOT / "contracts",
        ("pension_agent.agent.orchestration", "pension_agent.agent.search")
        + tuple(f"pension_agent.agent.{name}" for name in DOMAIN_PACKAGES),
    )


def test_orchestration_does_not_select_concrete_domain_agents() -> None:
    _assert_no_imports(
        AGENT_ROOT / "orchestration",
        tuple(f"pension_agent.agent.{name}" for name in DOMAIN_PACKAGES),
    )


def test_search_agent_does_not_depend_on_orchestration_or_domain_agents() -> None:
    _assert_no_imports(
        AGENT_ROOT / "search",
        ("pension_agent.agent.orchestration",)
        + tuple(f"pension_agent.agent.{name}" for name in DOMAIN_PACKAGES),
    )


@pytest.mark.parametrize("domain_package", DOMAIN_PACKAGES)
def test_domain_agents_are_independent(domain_package: str) -> None:
    other_domains = tuple(name for name in DOMAIN_PACKAGES if name != domain_package)
    _assert_no_imports(
        AGENT_ROOT / domain_package,
        ("pension_agent.agent.orchestration",)
        + tuple(f"pension_agent.agent.{name}" for name in other_domains),
    )


@pytest.mark.parametrize("module_name", ["retrieval", "rules"])
def test_infrastructure_and_rules_do_not_depend_on_agents(module_name: str) -> None:
    _assert_no_imports(PACKAGE_ROOT / module_name, ("pension_agent.agent",))
