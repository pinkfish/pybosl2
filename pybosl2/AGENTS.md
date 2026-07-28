# AGENTS.md

## Project Context

- **Language**: Python 3.11+
- **Environment**: Strict type-checking, automated linting, and rigorous documentation standards.

## Code Style & Formatting Rules

- Always use standard Python style guides unless explicitly overridden here.
- Maximize clarity by using short, cohesive functions under 50 lines long.
- Do not emit code containing `TODO` comments or stubbed code segments.
- For all the doc strings, classes too, add a single line summary first and then a blank line and a description.

## 1. Type Hinting Guide

AI agents must enforce strict, static type safety across the entire repository.

### Rules

- **Total Coverage**: Every function, method, parameter, and return value requires explicit type hints.
- **No Implicit Any**: Do not use `Any` unless it is functionally unavoidable.
- **Modern Syntax**: Use native pipe operators `|` for unions and built-in collection classes instead of the legacy `typing` module.
- **Local Variable Annotations**: Explicitly type complex intermediate variables, collection initializations, or API payloads.
- **Generic Constraints**: Define structural interfaces with `Protocol` or apply explicit variance rules on `TypeVar`.
- **Python usgae**: Make sure to use built in python
maths systems and other built in python mechanisms rather
than making a new one.
- **Paths**: For all lists of paths use the Paths object,
list[Sequence[float]] or numpy arrays should use paths.
- **Type overrides**: avoid type mixing in overrides, dont
do 'float | list[float]' change it to handle only the list.

### Good Implementation Example

```python
from collections.abc import Mapping, Sequence
from typing import Protocol, TypeVar

T = TypeVar("T", covariant=True)


class Renderable(Protocol[T]):
    def render(self) -> str: ...


def process_items(items: Sequence[Renderable[str]], config: Mapping[str, int | float]) -> list[str]:
    """Process a sequence of generic renderable items based on local configuration details."""
    results: list[str] = []
    limit: int | float = config.get("max_length", 100)

    for item in items:
        rendered: str = item.render()
        if len(rendered) <= limit:
            results.append(rendered)

    return results
```

### Bad Implementation Example

```python
# AVOID: Missing types, legacy Union/List syntax, and implicit Any usage.
from typing import List, Union


def process_items(items, config: dict):
    results = []  # Untyped empty collection
    for item in items:
        results.append(item.render())
    return results
```

## 2. Documentation & Docstring Guide

AI agents must write fully populated docstrings that explicitly match the target code.

### Rules

- **Format style**: Adhere strictly to the Google Python Style Guide for all docstrings.
- **Mandatory Fields**: Every public module, class, and function must include an explanatory docstring overview.
- **Section Breaks**: Delineate `Args:`, `Returns:`, and `Raises:` arguments with clear line breaks.
- **No Type Redundancy**: Do not duplicate type names inside the docstrings text; rely exclusively on the source type hints.
- **Error Transparency**: Every exception explicitly thrown in the function block must be declared under a `Raises:` header.

### Good Implementation Example

```python
def fetch_user_profile(user_id: int, timeout_seconds: float = 5.0) -> dict[str, str]:
    """Retrieves comprehensive account credentials for a verified user profile.

    This function queries the database backend directly to parse core identity schemas.

    Args:
        user_id: The unique database row identifier assigned to the user profile.
        timeout_seconds: Maximum duration in seconds to wait before terminating the request.

    Returns:
        A map containing verified user account attributes such as email and username status.

    Raises:
        ValueError: If the requested user_id is zero or structurally malformed.
        ConnectionError: If the remote authentication database times out.
    """
    if user_id <= 0:
        raise ValueError("The provided user account identifier must be a positive integer.")
    ...
```

### Bad Implementation Example

```python
def fetch_user_profile(user_id: int, timeout_seconds: float = 5.0) -> dict[str, str]:
    """Fetches profiles.

    :param user_id: int (AVOID: Redundant type listing and non-Google style layout)
    :returns: dict
    """
    ...
```

## Validation & Verification Commands

Always test modifications locally before finalizing suggestions or submitting pull requests:
- **Type Check**: `mypy --strict .`
- **Lint & Format**: `ruff check . --fix` and `ruff format .`
