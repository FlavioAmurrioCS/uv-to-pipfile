from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import tempfile
from typing import TYPE_CHECKING
from typing import NamedTuple

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from argparse import Namespace
    from collections.abc import Generator

    from typing_extensions import Literal
    from typing_extensions import NotRequired
    from typing_extensions import Self
    from typing_extensions import TypeAlias
    from typing_extensions import TypedDict

    class _PipenvPackage(TypedDict):
        extras: NotRequired[list[str]]
        hashes: list[str]
        markers: NotRequired[str]
        version: str

    class _PipenvEditablePackage(TypedDict):
        editable: Literal[True]
        extras: NotRequired[list[str]]
        file: str
        markers: NotRequired[str]

    class _PipenvGitPackage(TypedDict):
        extras: NotRequired[list[str]]
        git: str
        markers: NotRequired[str]
        ref: str

    PipenvPackage: TypeAlias = "_PipenvPackage | _PipenvEditablePackage | _PipenvGitPackage"

    class _PipfileLockSource(TypedDict):
        name: str
        url: str
        verify_ssl: bool

    _PipfileLockMeta = TypedDict(
        "_PipfileLockMeta",
        {
            "hash": dict[Literal["sha256"], str],
            "pipfile-spec": Literal[6],
            "requires": dict[Literal["python_version"], str],
            "sources": list[_PipfileLockSource],
        },
    )

    class PipfileLock(TypedDict):
        _meta: _PipfileLockMeta
        default: dict[str, PipenvPackage]
        develop: dict[str, PipenvPackage]


logger = logging.getLogger(__name__)


class Args(NamedTuple):
    uv_lock: str
    python: str | None
    index_url: str | None

    @staticmethod
    def parser() -> ArgumentParser:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--uv-lock", default="uv.lock")
        parser.add_argument("--python", default=None)
        parser.add_argument("--index-url", default=None)
        return parser

    @classmethod
    def _namespace_to_self(cls, namespace: Namespace) -> Self:
        return cls(**vars(namespace))

    @classmethod
    def parse_args(cls, argv: list[str] | tuple[str, ...] | None = None) -> Self:
        parser = Args.parser()
        known_args = parser.parse_args(argv)
        return cls._namespace_to_self(known_args)

    @classmethod
    def parse_known_args(
        cls, argv: list[str] | tuple[str, ...] | None = None
    ) -> tuple[Self, list[str]]:
        parser = Args.parser()
        known_args, rest = parser.parse_known_args(argv)
        return cls._namespace_to_self(known_args), rest


@contextlib.contextmanager
def chdir(path: str) -> Generator[None]:
    original = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


def get_python_version(cwd: str) -> str | None:
    with chdir(cwd):
        if os.path.exists("Pipfile.lock"):
            with open("Pipfile.lock") as f:
                data: PipfileLock = json.load(f)
                return data["_meta"]["requires"]["python_version"]
        if os.path.exists("Pipfile"):
            with open("Pipfile") as f:
                for line in f:
                    if line.startswith("python_version"):
                        _, _, version = line.partition("=")
                        return version.strip().strip("\"'")
        if os.path.exists(".python-version"):
            with open(".python-version") as f:
                return f.read().strip()
    return None


def get_index_url(cwd: str) -> str | None:
    with chdir(cwd):
        if os.path.exists("Pipfile.lock"):
            with open("Pipfile.lock") as f:
                data: PipfileLock = json.load(f)
                sources = data["_meta"]["sources"]
                if sources:
                    return sources[0]["url"]
    return None


def parse_requirements(requirements_txt: str) -> tuple[dict[str, PipenvPackage], str]:  # noqa: C901, PLR0912, PLR0915
    ret: dict[str, PipenvPackage] = {}
    _index = ""
    with open(requirements_txt) as f:
        hashes = []
        for _line in f:
            line = _line.strip("\n \\")
            if not line:
                continue
            if line.startswith("#"):
                continue
            if line.startswith("-i "):
                _index = line.split("-i ")[-1]
                continue
            if line.startswith("--hash="):
                hashes.append(line.split("--hash=")[-1])
                continue

            hashes.sort()
            hashes = []

            package, _, markers = line.partition(";")
            package = package.strip()
            markers = markers.strip()

            pkg: PipenvPackage
            extras = ""
            name = "NOTHING"

            if package.startswith("-e "):
                project_dir = os.path.abspath(package.split("-e ")[-1])
                pyproject_path = os.path.join(project_dir, "pyproject.toml")
                name = os.path.basename(project_dir)
                if os.path.exists(pyproject_path):
                    pattern = re.compile(r'name\s*=\s*["\']([^"\']+)["\']')
                    with open(pyproject_path) as pf:
                        for mline in pf:
                            match = pattern.search(mline)
                            if match:
                                name = match.group(1)
                                break

                pkg = {
                    "editable": True,
                    "file": line.split("-e ")[-1],
                }
            elif "git+" in package:
                name, _, git_full = package.partition("@")
                if "[" in name:
                    name, extras = line.strip("]").split("[", maxsplit=1)
                url, _, ref = git_full.partition("@")
                _vcs, _, git = url.partition("+")
                pkg = {
                    "git": git,
                    "ref": ref,
                }
            else:
                name, _, version = package.partition("==")
                extras = ""
                if "[" in name:
                    name, extras = line.strip("]").split("[", maxsplit=1)
                pkg = {
                    "hashes": hashes,
                    "version": f"=={version}",
                }

            if markers:
                pkg["markers"] = markers
            if extras:
                pkg["extras"] = extras.split(",")
            ret[name] = pkg
    return ret, _index


def uv_approach(
    python_version: str, args: Args, rest: list[str]
) -> tuple[dict[str, PipenvPackage], dict[str, PipenvPackage], str]:
    cwd = os.path.abspath(os.path.dirname(args.uv_lock))
    with tempfile.NamedTemporaryFile() as requirements_txt:
        cmd = (
            "uv",
            "export",
            f"--python={python_version}",
            "--format=requirements.txt",
            "--no-annotate",
            "--no-header",
            "--quiet",
            "--locked",
            f"--output-file={requirements_txt.name}",
        )

        _result = subprocess.run((*cmd, "--no-dev"), check=True, cwd=cwd, text=True)  # noqa: S603
        default_packages, index = parse_requirements(requirements_txt.name)

        index_url = (
            args.index_url
            or index
            or get_index_url(cwd)
            or os.getenv("PIP_INDEX_URL")
            or os.getenv("UV_INDEX_URL")
            or "https://pypi.org/simple"
        )

        dev_flags = ("--all-extras", "--all-groups")
        _result = subprocess.run((*cmd, *dev_flags, *rest), check=True, cwd=cwd, text=True)  # noqa: S603
        dev_packages = {
            k: v
            for k, v in parse_requirements(requirements_txt.name)[0].items()
            if k not in default_packages
        }
    return default_packages, dev_packages, index_url


def main(argv: list[str] | tuple[str, ...] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s"
    )
    args, rest = Args.parse_known_args(argv)
    cwd = os.path.abspath(os.path.dirname(args.uv_lock))

    python_version = args.python or get_python_version(cwd) or "3.12"

    with open(os.path.join(cwd, ".python-version"), "w") as f:
        f.write(python_version + "\n")

    default_packages, dev_packages, index_url = uv_approach(python_version, args, rest)

    data: PipfileLock = {
        "_meta": {
            "hash": {"sha256": "UVLOCK"},
            "pipfile-spec": 6,
            "requires": {"python_version": python_version},
            "sources": [{"name": "pypi", "url": index_url, "verify_ssl": True}],
        },
        "default": default_packages,
        "develop": dev_packages,
    }

    with open(os.path.join(cwd, "Pipfile.lock"), "w") as f:
        json.dump(data, f, indent=2)

    with open(os.path.join(cwd, "Pipfile"), "w") as f:
        f.write("[requires]\n")
        f.write(f'python_version = "{python_version}"\n')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
