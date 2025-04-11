# uv-to-pipfile

A pre-commit hook to convert `uv.lock` files to `Pipfile.lock` format.

## Using uv-to-pipfile with pre-commit

Add this to your `.pre-commit-config.yaml`:

```yaml
-   repo: https://github.com/FlavioAmurrioCS/uv-to-pipfile
    rev: 0.0.1  # Use the ref you want to point at
    hooks:
    -   id: uv-to-pipfile
```
