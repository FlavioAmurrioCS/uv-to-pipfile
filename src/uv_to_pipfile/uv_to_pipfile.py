#!/usr/bin/env pipx run
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "tomli>=1.1.0 ; python_full_version < '3.11'",
# ]
# ///
from __future__ import annotations

import os
import re
import sys

if os.getenv("GET_VENV") == "1":
    print(sys.executable)
    raise SystemExit(0)
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from typing import Final
    from typing import List
    from typing import TypedDict
    from typing import Union

    from _typeshed import Incomplete
    from typing_extensions import NotRequired
    from typing_extensions import TypeAlias
    from typing_extensions import TypeGuard

    class Sdist(TypedDict):
        url: str
        hash: str
        size: int

    class RegistrySource(TypedDict):
        registry: str

    class GitSource(TypedDict):
        git: str

    class VirtualSource(TypedDict):
        virtual: str

    class RequiresDist(TypedDict):
        name: str
        specifier: NotRequired[str]
        git: NotRequired[str]

    class RequiresDevDev(TypedDict):
        name: str
        specifier: str

    class RequiresDev(TypedDict):
        dev: list[RequiresDevDev]

    Metadata = TypedDict(
        "Metadata",
        {
            "requires-dist": List[RequiresDist],
            "requires-dev": RequiresDev,
        },
    )

    class DevDependenciesDev(TypedDict):
        name: str

    class DevDependencies(TypedDict):
        dev: list[DevDependenciesDev]

    class Dependency(TypedDict):
        name: str
        marker: NotRequired[str]

    class RegistryPackage(TypedDict):
        name: str
        version: str
        source: RegistrySource
        dependencies: NotRequired[list[Dependency]]
        sdist: NotRequired[Sdist]
        wheels: NotRequired[list[Sdist]]

    class GitPackage(TypedDict):
        name: str
        version: str
        source: GitSource
        dependencies: NotRequired[list[Dependency]]

    VirtualPackage = TypedDict(
        "VirtualPackage",
        {
            "name": str,
            "version": str,
            "source": VirtualSource,
            "dependencies": NotRequired[List[Dependency]],
            "dev-dependencies": NotRequired[DevDependencies],
            "metadata": Metadata,
        },
    )

    Package: TypeAlias = Union[RegistryPackage, GitPackage, VirtualPackage]

    UVLock = TypedDict(
        "UVLock",
        {
            "version": int,
            "revision": int,
            "requires-python": str,
            "package": List[Package],
        },
    )


def is_virtual_package(package: Package) -> TypeGuard[VirtualPackage]:
    return "virtual" in package["source"]


def is_registry_package(package: Package) -> TypeGuard[RegistryPackage]:
    return "registry" in package["source"]


def is_git_package(package: Package) -> TypeGuard[GitPackage]:
    return "git" in package["source"]


###############################################################################


def registry_package_to_dict(package: RegistryPackage) -> dict[str, Any]:
    hashes = []
    if "sdist" in package:
        hashes.append(package["sdist"]["hash"])
    if "wheels" in package:
        hashes.extend([wheel["hash"] for wheel in package["wheels"]])
    return {
        "hashes": hashes,
        "version": f"=={package['version']}",
    }


def git_package_to_dict(package: GitPackage) -> dict[str, Any]:
    git, ref = package["source"]["git"].split("#")
    return {
        "git": git,
        "ref": ref,
    }


def load_toml(file: str) -> Incomplete:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomli as tomllib
        except ImportError:
            script_name = os.path.basename(__file__)
            print("Please do ONE of the following:")
            print(" - Run this script with Python >=3.11")
            print(" - Run this script with PEP723 compliant tools such as:")
            print(f"   - pipx run {script_name}")
            print(f"   - uv run {script_name}")
            print(f"   - hatch run {script_name}")
            raise
    with open(file, "rb") as f:
        return tomllib.load(f)


def parse_args(args: list[str] | None) -> tuple[str, str]:
    import argparse

    parser = argparse.ArgumentParser(description="Convert uv.lock to Pipfile.lock")
    parser.add_argument(
        "--uv-lock",
        type=str,
        default="./uv.lock",
        required=False,
        help="Path to the uv.lock file (default: %(default)s)",
    )
    parser.add_argument(
        "--pipfile-lock",
        type=str,
        default="./Pipfile.lock",
        required=False,
        help="Path to the Pipfile.lock file (default: %(default)s)",
    )
    parsed_args = parser.parse_args(args)
    uv_lock = os.path.abspath(parsed_args.uv_lock)
    pipfile_lock = os.path.abspath(parsed_args.pipfile_lock)
    if not os.path.exists(uv_lock):
        print(f"File {uv_lock} does not exist.")
        raise SystemExit(1)
    return uv_lock, pipfile_lock

def python_version(uv_lock: str ) -> str:
    basedir = os.path.dirname(uv_lock)
    python_version_file = os.path.join(basedir, ".python_version")
    if os.path.exists(python_version_file):
        with open(python_version_file) as f:
            return f.read().strip()

    data: UVLock = load_toml(uv_lock)
    if "requires-python" in data:
        pattenr = re.compile(r"3\.(\d+)")
        match = pattenr.search(data["requires-python"])
        if match:
            version = match.group(1)
            if version.isdigit():
                return f"3.{version}"
    return "3.11"



def main(args: list[str] | None = None) -> int:  # noqa: C901, PLR0912
    uv_lock, pipfile_lock = parse_args(args)

    if not os.path.exists(uv_lock):
        print(f"File {uv_lock} does not exist.")
        return 1
    data: UVLock = load_toml(uv_lock)

    git_packages: dict[str, GitPackage] = {}
    registry_packages: dict[str, RegistryPackage] = {}
    virtual_packages: dict[str, VirtualPackage] = {}

    for package in data["package"]:
        if is_virtual_package(package):
            virtual_packages[package["name"]] = package
        elif is_git_package(package):
            git_packages[package["name"]] = package
        elif is_registry_package(package):
            registry_packages[package["name"]] = package
        else:
            print(package)

    if len(virtual_packages) != 1:
        print(f"Expected exactly one virtual package, got {len(virtual_packages)}")
        return 1
    virtual_package = virtual_packages.popitem()[1]

    registry = {x["source"]["registry"] for x in registry_packages.values()}
    if len(registry) != 1:
        print(f"Expected exactly one registry, got {len(registry)}")

    selected_registry = registry.pop()

    pipfile_lock_data: Final = {
        "_meta": {
            "hash": {"sha256": "UVLOCK"},
            "pipfile-spec": 6,
            "requires": {"python_version": python_version(uv_lock)},
            "sources": [{"name": "pypi", "url": selected_registry, "verify_ssl": True}],
        },
        "default": {},
        "develop": {},
    }

    queue: deque[str] = deque()
    queue.extend([dep["name"] for dep in virtual_package.get("dependencies", [])])

    while queue:
        dep_name = queue.popleft()
        if dep_name in git_packages:
            package = git_packages[dep_name]
            pipfile_lock_data["default"][dep_name] = git_package_to_dict(package)
            queue.extend([dep["name"] for dep in package.get("dependencies", [])])
        elif dep_name in registry_packages:
            package = registry_packages[dep_name]
            pipfile_lock_data["default"][dep_name] = registry_package_to_dict(package)
            queue.extend([dep["name"] for dep in package.get("dependencies", [])])

    queue.extend(
        [dep["name"] for dep in virtual_package.get("dev-dependencies", {}).get("dev", [])]
    )

    while queue:
        dep_name = queue.popleft()
        if dep_name in git_packages:
            package = git_packages[dep_name]
            pipfile_lock_data["develop"][dep_name] = git_package_to_dict(package)
            queue.extend([dep["name"] for dep in package.get("dependencies", [])])
        elif dep_name in registry_packages:
            package = registry_packages[dep_name]
            pipfile_lock_data["develop"][dep_name] = registry_package_to_dict(package)
            queue.extend([dep["name"] for dep in package.get("dependencies", [])])

    with open(pipfile_lock, "w") as f:
        import json

        json.dump(pipfile_lock_data, f, indent=4, sort_keys=True)

    return 0


# @app.command()
# def sort_json(file: str):
#     """
#     Sort a JSON file.
#     """
#     with open(file, "r") as f:
#         data = json.load(f)
#     for name, package in data.get("default", {}).items():
#         if "hashes" in package:
#             package["hashes"].sort()
#     for name, package in data.get("develop", {}).items():
#         if "hashes" in package:
#             package["hashes"].sort()
#     output_file = "sorted_" + os.path.basename(file)
#     with open(output_file, "w") as f:
#         json.dump(data, f, indent=4, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
