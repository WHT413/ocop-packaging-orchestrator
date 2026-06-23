from __future__ import annotations

from pathlib import Path

import pytest

from ocop_pack.services.validation_service import load_project


@pytest.fixture()
def example_project():
    return load_project(Path("examples/projects/tea_basic/project.yaml"))
