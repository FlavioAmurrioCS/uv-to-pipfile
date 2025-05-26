from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import Literal

if TYPE_CHECKING:
    from typing import TypedDict
    from typing import Union

    from typing_extensions import TypeAlias

    class Uv(TypedDict):
        sources: dict[str, dict[str, str]]

    class Tool(TypedDict):
        uv: Uv

    Project = TypedDict(
        "Project",
        {
            "name": str,
            "version": str,
            "description": str,
            "readme": str,
            "requires-python": str,
            "dependencies": list[str],
        },
    )

    PyProject = TypedDict(
        "PyProject",
        {
            "project": Project,
            "tool": Tool,
            "dependency-groups": dict[str, list[str]],
        },
    )

    class Source(TypedDict):
        url: str
        verify_ssl: bool
        name: str

    class Requires(TypedDict):
        python_version: str

    Packages: TypeAlias = "dict[str, Union[str, dict[str,str]]]"

    Pipfile = TypedDict(
        "Pipfile",
        {
            "source": list[Source],
            "packages": Packages,
            "dev-packages": Packages,
            "requires": Requires,
        },
    )

    PipfileLockMeta = TypedDict(
        "PipfileLockMeta",
        {
            "hash": dict[str, str],
            "pipfile-spec": int,
            "requires": dict[Literal["python_version"], str],
            "sources": list[Source],
        },
    )
    PipfileLock = TypedDict(  # noqa: UP013
        "PipfileLock",
        {
            "_meta": PipfileLockMeta,
            "default": dict[str, dict[str, list[str]]],
            "develop": dict[str, dict[str, list[str]]],
        },
    )
