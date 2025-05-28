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
from typing import NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any
    from typing import Final
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

    class EditableSource(TypedDict):
        editable: str

    class Dependency(TypedDict):
        name: str
        marker: NotRequired[str]
        specifier: NotRequired[str]
        extras: NotRequired[list[str]]

    Metadata = TypedDict(
        "Metadata",
        {
            "requires-dist": list[Dependency],
            "requires-dev": NotRequired[dict[str, list[Dependency]]],
        },
    )

    class DevDependencies(TypedDict):
        dev: list[Dependency]

    RegistryPackage = TypedDict(
        "RegistryPackage",
        {
            "name": str,
            "version": str,
            "source": RegistrySource,
            "dependencies": NotRequired[list[Dependency]],
            "sdist": NotRequired[Sdist],
            "wheels": NotRequired[list[Sdist]],
            "optional-dependencies": NotRequired[dict[str, list[Dependency]]],
        },
    )

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
            "dependencies": NotRequired[list[Dependency]],
            "dev-dependencies": NotRequired[DevDependencies],
            "metadata": Metadata,
        },
    )

    EditablePackage = TypedDict(
        "EditablePackage",
        {
            "name": str,
            "version": str,
            "source": EditableSource,
            "dependencies": NotRequired[list[Dependency]],
            "dev-dependencies": NotRequired[DevDependencies],
            "metadata": Metadata,
        },
    )

    RootPackage: TypeAlias = Union[EditablePackage, VirtualPackage]

    Package: TypeAlias = Union[RegistryPackage, GitPackage, RootPackage]

    UVLock = TypedDict(
        "UVLock",
        {
            "version": int,
            "revision": int,
            "requires-python": str,
            "package": list[Package],
        },
    )


def is_root_package(package: Package) -> TypeGuard[RootPackage]:
    return (is_virtual_package(package) or is_editable_package(package)) and "metadata" in package


def is_editable_package(package: Package) -> TypeGuard[EditablePackage]:
    return "editable" in package["source"]


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
    extras = list(package.get("optional-dependencies", {}).keys())
    return {
        **({} if not extras else {"extras": extras}),
        "hashes": hashes,
        "version": f"=={package['version']}",
    }


def git_package_to_dict(package: GitPackage) -> dict[str, Any]:
    git, ref = package["source"]["git"].split("#")
    return {
        "git": git,
        "ref": ref,
    }


def editable_package_to_dict(package: EditablePackage) -> dict[str, Any]:
    return {
        "editable": True,
        "path": os.path.relpath(os.path.realpath(package["source"]["editable"]), os.getcwd()),
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


def python_version(uv_lock: str) -> str:
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


class ParsedPackages(NamedTuple):
    git_packages: dict[str, GitPackage]
    registry_packages: dict[str, RegistryPackage]
    root_package: RootPackage
    editable_packages: dict[str, EditablePackage]
    virtual_packages: dict[str, VirtualPackage]


def parse_packages(
    uv_lock: str,
) -> ParsedPackages:
    data: UVLock = load_toml(uv_lock)
    git_packages: dict[str, GitPackage] = {}
    registry_packages: dict[str, RegistryPackage] = {}
    root_packages: dict[str, RootPackage] = {}
    editable_packages: dict[str, EditablePackage] = {}
    virtual_packages: dict[str, VirtualPackage] = {}

    for package in data["package"]:
        if is_root_package(package):
            root_packages[package["name"]] = package
        elif is_git_package(package):
            git_packages[package["name"]] = package
        elif is_registry_package(package):
            registry_packages[package["name"]] = package
        elif is_editable_package(package):
            editable_packages[package["name"]] = package
        elif is_virtual_package(package):
            virtual_packages[package["name"]] = package
        else:
            print(package)

    if len(root_packages) != 1:
        print(f"Expected exactly one root package, got {len(root_packages)}")
    root_package = root_packages.popitem()[1]
    return ParsedPackages(
        git_packages=git_packages,
        registry_packages=registry_packages,
        root_package=root_package,
        editable_packages=editable_packages,
        virtual_packages=virtual_packages,
    )


def get_sources(registry_packages: Iterable[RegistryPackage]) -> list[dict[str, Any]]:
    registries = {x["source"]["registry"] for x in registry_packages}
    return [{"name": registry, "url": registry, "verify_ssl": True} for registry in registries]


def main(args: list[str] | None = None) -> int:  # noqa: C901, PLR0912, PLR0915
    uv_lock, pipfile_lock = parse_args(args)

    parsed_packages = parse_packages(uv_lock)
    git_packages = parsed_packages.git_packages
    registry_packages = parsed_packages.registry_packages
    root_package = parsed_packages.root_package
    editable_packages = parsed_packages.editable_packages
    # virtual_packages = parsed_packages.virtual_packages

    sources = get_sources(registry_packages.values()) or [
        {"name": "default", "url": "https://pypi.org/simple", "verify_ssl": True}
    ]

    if len(sources) != 1:
        print(f"Expected exactly one registry, got {len(sources)}")

    pipfile_lock_data: Final = {
        "_meta": {
            "hash": {"sha256": "UVLOCK"},
            "pipfile-spec": 6,
            "requires": {"python_version": python_version(uv_lock)},
            "sources": sources,
        },
        "default": {},
        "develop": {},
    }

    queue: deque[Dependency] = deque()
    queue.extend(root_package["metadata"]["requires-dist"])
    if is_editable_package(root_package):
        pipfile_lock_data["default"][root_package["name"]] = editable_package_to_dict(root_package)

    cumulative_dependencies = set()

    while queue:
        dep = queue.popleft()
        dep_name = dep["name"]
        if dep_name in cumulative_dependencies:
            continue
        cumulative_dependencies.add(dep_name)
        if dep_name in git_packages:
            git_package = git_packages[dep_name]
            pipfile_lock_data["default"][dep_name] = git_package_to_dict(git_package)
            queue.extend(git_package.get("dependencies", []))
        elif dep_name in registry_packages:
            registry_package = registry_packages[dep_name]
            pipfile_lock_data["default"][dep_name] = registry_package_to_dict(registry_package)
            queue.extend(registry_package.get("dependencies", []))
            for pkg in registry_package.get("optional-dependencies", {}).values():
                queue.extend(pkg)
        elif dep_name in editable_packages:
            editable_package = editable_packages[dep_name]
            pipfile_lock_data["default"][dep_name] = editable_package_to_dict(editable_package)
            queue.extend(editable_package.get("dependencies", []))

    queue.extend(root_package["metadata"].get("requires-dev", {}).get("dev", []))

    cumulative_dependencies = set()
    while queue:
        dep = queue.popleft()
        dep_name = dep["name"]
        if dep_name in cumulative_dependencies:
            continue
        cumulative_dependencies.add(dep_name)
        if dep_name in git_packages:
            git_package = git_packages[dep_name]
            pipfile_lock_data["develop"][dep_name] = git_package_to_dict(git_package)
            queue.extend(git_package.get("dependencies", []))
        elif dep_name in registry_packages:
            registry_package = registry_packages[dep_name]
            pipfile_lock_data["develop"][dep_name] = registry_package_to_dict(registry_package)
            queue.extend(registry_package.get("dependencies", []))
            for pkg in registry_package.get("optional-dependencies", {}).values():
                queue.extend(pkg)
        elif dep_name in editable_packages:
            editable_package = editable_packages[dep_name]
            pipfile_lock_data["develop"][dep_name] = editable_package_to_dict(editable_package)
            queue.extend(editable_package.get("dependencies", []))

    with open(pipfile_lock, "w") as f:
        import json

        json.dump(pipfile_lock_data, f, indent=4, sort_keys=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
