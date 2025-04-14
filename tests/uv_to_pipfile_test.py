from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from tests.utils import extract_deps
from tests.utils import work_in_temp_directory
from uv_to_pipfile.uv_to_pipfile import main

if TYPE_CHECKING:
    from tests._types import PipfileLock


def compare_pipfile_locks(
    original: PipfileLock,
    generated: PipfileLock,
) -> None:
    """
    Compare two Pipfile.lock files.
    """
    all_default = set(original["default"].keys()).union(set(generated["default"].keys()))
    all_develop = set(original["develop"].keys()).union(set(generated["develop"].keys()))
    # Similar the one below, we need to take into account the markers from the metadata.
    all_develop.discard("colorama")

    # Seems like the depending how the depedency is specifies in the metadata will affect how it
    # gets listed in the section dependencies.
    all_develop.discard("requests")

    for key in all_default:
        assert key in original["default"]
        assert key in generated["default"]
        original["default"][key].pop("markers", None)
        original["default"][key].pop("index", None)
        _original_hashes: list[str] = original["default"][key].pop("hashes", [])  # pyright: ignore[reportAssignmentType]
        _generated_hashes: list[str] = generated["default"][key].pop("hashes", [])  # pyright: ignore[reportAssignmentType]
        for h in _generated_hashes:
            assert h in _original_hashes
        assert original["default"][key] == generated["default"][key]

    for key in all_develop:
        assert key in original["develop"]
        assert key in generated["develop"]
        original["develop"][key].pop("markers", None)
        original["develop"][key].pop("index", None)
        _original_hashes = original["develop"][key].pop("hashes", [])  # pyright: ignore[reportAssignmentType]
        _generated_hashes = generated["develop"][key].pop("hashes", [])  # pyright: ignore[reportAssignmentType]
        for h in _generated_hashes:
            assert h in _original_hashes
        assert original["develop"][key] == generated["develop"][key]


def test_foo() -> None:
    wd = Path(__file__).parent.joinpath("test_files", "variation1")
    with work_in_temp_directory():
        shutil.copy(wd.joinpath("pyproject.toml"), ".")
        shutil.copy(wd.joinpath(".python-version"), ".")
        with open("pyproject.toml") as f:
            content = f.read()
        extract_deps.cache_clear()
        original = extract_deps("pyproject.toml", content)

        del os.environ["VIRTUAL_ENV"]

        subprocess.run(  # noqa: S603
            ("uv", "lock"),
            check=True,
        )
        main(["--pipfile-lock", "Generate.Pipfile.lock"])
        with open("Generate.Pipfile.lock") as f:
            generated_pipfile_lock = json.load(f)
        # print(os.getcwd())
        try:
            compare_pipfile_locks(
                original,
                generated_pipfile_lock,
            )
        except:
            shutil.move("Pipfile.lock", "/tmp/Pipfile.lock")  # noqa: S108
            shutil.move("Generate.Pipfile.lock", "/tmp/Generated.Pipfile.lock")  # noqa: S108
            _sort_json_inplace("/tmp/Pipfile.lock")  # noqa: S108
            _sort_json_inplace("/tmp/Generated.Pipfile.lock")  # noqa: S108
            logging.error("Pipfile.lock comparison failed")  # noqa: LOG015, TRY400
            logging.error("code --diff /tmp/Pipfile.lock /tmp/Generated.Pipfile.lock")  # noqa: LOG015, TRY400
            raise


def _sort_json_inplace(file: str) -> None:
    """
    Sort a JSON file.
    """
    with open(file) as f:
        data = json.load(f)
    for package in data.get("default", {}).values():
        if "hashes" in package:
            package["hashes"].sort()
    for package in data.get("develop", {}).values():
        if "hashes" in package:
            package["hashes"].sort()
    with open(file, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True)
