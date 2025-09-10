# uv-to-pipfile

A tool and pre-commit hook to convert `uv.lock` files to `Pipfile.lock` format, allowing you to use [uv](https://github.com/astral-sh/uv) for dependency resolution while maintaining compatibility with Pipenv workflows.

## Installation

<!-- Install from PyPI:

```bash
pip install uv-to-pipfile
```

## Using uv-to-pipfile

### As a CLI Tool

Run directly from the command line:

```bash
# Convert uv.lock to Pipfile.lock in the current directory
uv-to-pipfile

# Specify an output file path
uv-to-pipfile --pipfile-lock custom_path/Pipfile.lock
``` -->

### With pre-commit

Add this to your `.pre-commit-config.yaml`:

```yaml
-   repo: https://github.com/FlavioAmurrioCS/uv-to-pipfile
    rev: v0.0.7  # Use the ref you want to point at
    hooks:
    -   id: uv-to-pipfile
```

## How it works

### Packages

The conversion process follows these steps:

- `uv.lock` lists packages as an array. We parse all of these and create a dictionary where the key is the package name and the value is the package metadata.
- We identify the virtual package which represents the project itself. This lists the dependencies.
- We create a queue with these packages and iterate through them, adding each to the respective section (default or develop).
- We then add their dependencies to the queue and continue processing.
- We repeat the same process for dev packages.

### Python Version Detection

The tool determines Python version requirements in the following order:

1. Check for a `.python-version` file in the same directory as the `uv.lock` file
2. Extract the `requires-python` field from the `uv.lock` (ignoring range markers such as `>=`)
3. Default to Python 3.11 if no version information is found

## Python Version Compatibility

This tool is compatible with Python 3.8 and later versions. The implementation is designed to work seamlessly across different Python environments:

- For Python 3.11+: No additional dependencies are required as `tomllib` is included in the standard library
- For Python 3.8-3.10: The `tomli` package is automatically installed as a dependency

The script can be executed in several ways:
- As an installed package via `uv-to-pipfile` command
- Directly as a PEP 723 compliant script using `pipx run`, `hatch run`, or `uv run`
- With Python 3.11+ using standard `python uv_to_pipfile.py`

## Known Issues and Limitations

- `uv.lock` does not provide markers information. Pipenv doesn't seem to mind this omission.
- `uv.lock` does not list all the hashes for a specific version. Some hashes might be filtered out.
  - Potential solution: Call the PyPI API to fetch missing hashes
  - Challenge: Additional work would be needed to support non-REST pip indexes like Artifactory
- The `_meta.hash.sha256` value will be missing from generated `Pipfile.lock` files. This appears to be a hash of the Pipfile and doesn't seem necessary.
- Currently, the tool only supports one index. Multi-index support could be added if needed.
- System-specific dependencies might be handled differently:
  - For example, `colorama` is only needed on Windows machines
  - It may not be listed in the original `Pipfile.lock` but gets listed in `uv.lock`
  - Installing the generated `Pipfile.lock` might install packages not strictly needed on your platform
- Dependencies installed in different ways across package sections may have different mappings:
  - For example, if `requests` is installed from a git source in main packages and as a transitive dependency from PyPI in dev packages
  - In Pipenv, it will be listed with the git URL and ref hash in main dependencies but with package name and version in dev dependencies
  - Potential fix: Forward metadata from the virtual root package, which would populate the correct fields depending on how it's listed

## Development Roadmap

The following enhancements are planned for future releases:

### Code Improvements
- Refactor package traversal logic to eliminate code duplication between main and dev package handling
- Move type definitions into a separate module to improve code organization
- Add type validation using Pydantic TypeAdapter to ensure proper type definitions

### Testing Enhancements
- Improve test infrastructure by adding direct `uv` and `pipenv` execution capabilities
- Implement integration tests that compare virtual environments created from both `uv.lock` and `Pipfile.lock`
- Optimize test performance:
  - Current approach: Generate `uv.lock`, then use `pipenv install <deps...>` for dependency resolution
  - Planned approach: Create `requirements.txt` from `uv` with pinned versions, then use with `pipenv`

### Feature Development
- Implement recursive approach for package traversal to simplify marker forwarding
- Add multi-index support for more complex dependency configurations
- Implement PyPI API integration to retrieve missing hashes
- Consider publishing as a PyPI package based on community adoption

## Contributing

Contributions are welcome! Feel free to open issues or pull requests on GitHub.

## License

MIT
