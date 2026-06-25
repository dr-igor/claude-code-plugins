# Python Coding Conventions

## Version

- Check project files for python versions supported/in-use (e.g., pyproject.toml, .python-version, etc.)
- If none found, support Python 3.10+

## Environment

Prefer `conda` environments over `venv` or other virtual environment tools.

## Dependency Management

Use `uv` and `pyproject.toml` for dependency management.

## Python-Specific Requirements

- Use `pathlib` for paths instead of `os.path`.
  - Prefer `Path` objects over string paths for filesystem operations.
  - Use `PurePosixPath` when manipulating paths as strings (e.g., for URLs) without filesystem access.
  - Accept `PathLike` types in function signatures for flexibility.
  - For an asynchronous filesystem interface, use `anyio.Path`.
- Liberally use generic types
- Prefer `dataclass`es, `NamedTuple`s, or `TypedDict`s for structured data, over simple tuples or dictionaries; for more complex cases, use `pydantic` models.
- Use f-strings for string interpolation.
- Use `Protocol`s to define structural types.

## Typing

- Use strict typing
- Use type hints in code you generate, even if existing code does not
- Take advantage of the latest typing features in the supported Python version (e.g. `ParamSpec`, `TypeGuard`, `Self`, etc.)
- Explicitly define type stubs for external libraries instead of using `# type: ignore` or `Any`.

## Error Handling

Follow the Pythonic principle of "Asking for forgiveness, not permission":

- Avoid defensive resource checks (file exists, is valid, etc.).
  - There is no reason to check if a resource exists or can be opened as expect (e.g. if it is a file when a directory is expected); if it doesn't exist or can't be used as expected, an exception will be raised when an attempt is made to use it.

## Tests

When asserting in a pytest test, assert on the full object, not each attribute/key separately; pytest will show the full detailed diff on failure.

## Clean Code Examples

### Declarative Code

```python
# ✓ Use Declarative - expresses intent directly
def get_active_user_emails(users: list[User]) -> list[str]:
    return [
        user.email.lower()
        for user in users
        if user.is_active
    ]

# ✗ Avoid Imperative - explicit step-by-step instructions
def get_active_user_emails(users: list[User]) -> list[str]:
    emails = []
    for user in users:
        if user.is_active:
            emails.append(user.email.lower())
    return emails
```

### Resource Cleanup

```python
# ✓ Use Context Manager for Resource Cleanup
from contextlib import contextmanager

@contextmanager
def database_transaction(db: Database):
    conn = db.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def update_user(user_id: int, data: dict) -> None:
    with database_transaction(db) as conn:
        conn.execute("UPDATE users SET ...", user_id, data)

# ✗ Avoid Manual Resource Management
def update_user(user_id: int, data: dict) -> None:
    conn = db.connect()
    ...  # perform operations
    conn.close() ## Risk of not closing on exceptions
```

## Frameworks and Libraries

- Prefer `typer` for CLI applications.
- Leverage `rich` for terminal output formatting and interactivity.
- Use `enlighten` for progress bars.
- Use `textual` for TUI applications.
