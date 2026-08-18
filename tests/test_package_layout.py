"""The scaffold must be importable as one installable application package."""

from importlib import import_module, resources

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "pension_agent.agent",
        "pension_agent.agent.answer_service",
        "pension_agent.agent.assembly",
        "pension_agent.agent.domains",
        "pension_agent.agent.domains.policy",
        "pension_agent.agent.domains.product",
        "pension_agent.agent.domains.tax_payout",
        "pension_agent.agent.search",
        "pension_agent.api",
        "pension_agent.config",
        "pension_agent.core",
        "pension_agent.ingest",
        "pension_agent.prompts",
        "pension_agent.retrieval",
        "pension_agent.rules",
    ],
)
def test_application_modules_are_importable(module_name: str) -> None:
    assert import_module(module_name) is not None


def test_runtime_resource_directories_are_packaged() -> None:
    package_root = resources.files("pension_agent")

    assert package_root.joinpath("config", "defaults").is_dir()
    assert package_root.joinpath("prompts").is_dir()
