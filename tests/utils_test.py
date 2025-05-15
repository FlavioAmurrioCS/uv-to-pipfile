from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from persistent_cache.decorators import persistent_cache

from uv_to_pipfile.uv_to_pipfile import load_toml

if TYPE_CHECKING:
    from collections.abc import Generator

    from tests._types_test import PipfileLock
    from tests._types_test import PyProject


@contextlib.contextmanager
def work_in_directory(tmp: str) -> Generator[None, None, None]:
    original_directory = os.getcwd()
    try:
        os.chdir(tmp)
        yield
    finally:
        os.chdir(original_directory)


@contextlib.contextmanager
def work_in_temp_directory() -> Generator[None, None, None]:
    with tempfile.TemporaryDirectory() as tmp, work_in_directory(tmp):
        yield


@persistent_cache(hours=1)
def extract_deps(pyproject: str, content: str) -> PipfileLock:  # noqa: ARG001
    """
    Convert a pyproject.toml file to a Pipfile.
    """
    ptoml: PyProject = load_toml(pyproject)

    version_file = Path(pyproject).parent.joinpath(".python_version")
    if version_file.exists():
        with open(version_file) as f:
            python_version = f.read().strip()
    else:
        match = re.search(r"3\.(\d+)", ptoml["project"]["requires-python"])
        python_version = f"3.{match.group(1)}" if match else "3.11"

    uv_source = ptoml["tool"]["uv"]["sources"]
    deps: list[str] = []
    for dep in ptoml["project"]["dependencies"]:
        if dep not in uv_source:
            deps.append(dep)
        else:
            deps.append(f"git+{uv_source[dep]['git']}#egg={dep}")

    dev_deps: list[str] = []
    for dep in ptoml["dependency-groups"].get("dev", []):
        if dep not in uv_source:
            dev_deps.append(dep)
        else:
            dev_deps.append(f"git+{uv_source[dep]['git']}#{dep}")

    subprocess.run(  # noqa: S603
        ("pipenv", "install", f"--python={python_version}"),
        check=True,
    )
    if deps:
        subprocess.run(  # noqa: S603
            ("pipenv", "install", *deps),
            check=True,
        )
    if dev_deps:
        subprocess.run(  # noqa: S603
            ("pipenv", "install", "--dev", *dev_deps),
            check=True,
        )
    with open("Pipfile.lock") as f:
        return json.load(f)
