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


def _from_import_modules(
    node: ast.ImportFrom,
    *,
    package_parts: tuple[str, ...],
) -> set[str]:
    if node.level == 0:
        return {node.module} if node.module is not None else set()

    relative_root = package_parts[: len(package_parts) - node.level + 1]
    if node.module is not None:
        return {".".join((*relative_root, node.module))}
    return {".".join((*relative_root, alias.name)) for alias in node.names}


def _absolute_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package_parts = path.relative_to(PACKAGE_ROOT.parent).parent.parts
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.update(_from_import_modules(node, package_parts=package_parts))
    return imports


def _assert_no_imports(directory: Path, forbidden_prefixes: tuple[str, ...]) -> None:
    violations: list[str] = []
    for path in _python_files(directory):
        for imported in _absolute_imports(path):
            if imported.startswith(forbidden_prefixes):
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} -> {imported}")
    assert violations == []


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("from ..policy import PolicyAgent", "pension_agent.agent.policy"),
        ("from .. import policy", "pension_agent.agent.policy"),
    ],
)
def test_relative_imports_are_resolved_to_absolute_modules(
    statement: str,
    expected: str,
) -> None:
    node = ast.parse(statement).body[0]

    assert isinstance(node, ast.ImportFrom)
    assert _from_import_modules(
        node,
        package_parts=("pension_agent", "agent", "orchestration"),
    ) == {expected}


def test_contracts_do_not_depend_on_agent_implementations() -> None:
    _assert_no_imports(
        AGENT_ROOT / "contracts",
        ("pension_agent.agent.orchestration", "pension_agent.agent.search")
        + tuple(f"pension_agent.agent.{name}" for name in DOMAIN_PACKAGES),
    )


def test_common_domain_runner_does_not_depend_on_react_or_domain_implementations() -> None:
    imports = _absolute_imports(AGENT_ROOT / "domain_runner.py")
    forbidden = (
        "langchain.agents",
        "langgraph",
        "pension_agent.agent.orchestration",
        "pension_agent.agent.search",
    ) + tuple(f"pension_agent.agent.{name}" for name in DOMAIN_PACKAGES)

    assert not any(imported.startswith(forbidden) for imported in imports)


def test_each_domain_package_owns_its_react_implementation() -> None:
    assert not (AGENT_ROOT / "domain_agent.py").exists()
    for domain_package in DOMAIN_PACKAGES:
        react_module = AGENT_ROOT / domain_package / "react.py"
        assert react_module.exists()
        assert "langchain.agents" in _absolute_imports(react_module)


def test_orchestration_does_not_select_concrete_domain_agents() -> None:
    _assert_no_imports(
        AGENT_ROOT / "orchestration",
        tuple(f"pension_agent.agent.{name}" for name in DOMAIN_PACKAGES),
    )


def test_search_service_does_not_depend_on_orchestration_or_domain_agents() -> None:
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


def test_api_does_not_import_retrieval_or_rules_directly() -> None:
    _assert_no_imports(
        PACKAGE_ROOT / "api",
        ("pension_agent.retrieval", "pension_agent.rules", "pension_agent.ingest"),
    )
