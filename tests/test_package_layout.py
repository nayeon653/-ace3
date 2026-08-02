"""The scaffold must be importable as one installable application package."""

from importlib import import_module, resources

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "pension_agent.agent",
        "pension_agent.config",
        "pension_agent.core",
        "pension_agent.ingest",
        "pension_agent.prompts",
        "pension_agent.retrieval",
        "pension_agent.rules",
        "pension_agent.server",
    ],
)
def test_application_modules_are_importable(module_name: str) -> None:
    assert import_module(module_name) is not None


def test_runtime_resource_directories_are_packaged() -> None:
    package_root = resources.files("pension_agent")

    assert package_root.joinpath("config", "defaults").is_dir()
    assert package_root.joinpath("prompts").is_dir()
