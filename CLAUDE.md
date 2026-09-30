# CLAUDE.md

## Python style

Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) for all Python code in this repository, including:

- Google-style docstrings (`Args:`, `Returns:`, `Raises:` sections) for modules, classes, and public functions.
- Type annotations on function signatures.
- Import whole modules/packages, not individual classes or functions (except from `typing`).
- Naming: `module_name`, `ClassName`, `function_name`, `CONSTANT_NAME`, `_private_name`.
- Maximum line length of 80 characters; 4-space indentation.
- No mutable default arguments; no bare `except:`.
