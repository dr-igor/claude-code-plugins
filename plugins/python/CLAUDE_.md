# Python Coding Guidelines

## Style & Conventions

- Follow PEP 8 for code style, PEP 257 for docstrings
- Use 4 spaces for indentation, never tabs
- Maximum line length of 88 characters (Black formatter standard)
- Use snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
- Organize imports: standard library, third-party, local (use isort)

## Type Hints & Data Structures

- Always use type hints for function signatures and class attributes
- Prefer `list[T]`, `dict[K, V]`, `set[T]` over `typing.List`, `typing.Dict` (Python 3.9+)
- Use `dataclasses` with `frozen=True` for immutable data, Pydantic for validation needs
- Use `TypedDict` for structured dictionaries, `Protocol` for structural subtyping
- Annotate return types explicitly, use `-> None` for functions without return values

## Modern Python Patterns

- Prefer list/dict/set comprehensions over loops for transformations
- Use `pathlib.Path` instead of `os.path` for file operations
- Use f-strings for string formatting, not `%` or `.format()`
- Use context managers (`with` statements) for resource management
- Prefer `enumerate()` over `range(len())`, `zip()` for parallel iteration

## Async & Concurrency

- Use `async`/`await` syntax exclusively, avoid callbacks
- Use `asyncio.gather()` for concurrent operations, `asyncio.create_task()` for fire-and-forget
- Always await async functions, never discard coroutines
- Use `asyncio.TaskGroup` (Python 3.11+) for structured concurrency
- Prefer async libraries (aiohttp, aiofiles) in async contexts

## Error Handling

- Raise specific exceptions, not generic `Exception`
- Create custom exception classes inheriting from appropriate base exceptions
- Use `raise ... from e` to preserve exception chains
- Don't use bare `except:`, always catch specific exception types
- Use context managers and EAFP ("Easier to Ask for Forgiveness than Permission")

## Testing

- Use `pytest` with fixtures for test setup/teardown
- Parametrize tests with `@pytest.mark.parametrize` for multiple input cases
- Use descriptive test function names: `test_<what>_<condition>_<expected>`
- Mock external dependencies with `unittest.mock` or `pytest-mock`
- Aim for testing behavior and public API, not implementation details
- Use `pytest.raises()` for exception testing, `pytest.approx()` for float comparisons

## Project Structure

- Use `pyproject.toml` for project configuration and dependencies
- Organize code into packages with clear `__init__.py` files
- Keep modules focused on a single responsibility
- Use `if __name__ == "__main__":` for executable modules
- Create a `src/` layout for installable packages

## Dependencies & Tooling

- Pin dependencies with version ranges in `pyproject.toml`
- Use `uv` or `poetry` for dependency management and virtual environments
- Run `ruff` for linting and formatting (replaces flake8, black, isort)
- Use `mypy` in strict mode for type checking
- Consider `pre-commit` hooks for automated checks

## Performance & Best Practices

- Use generators and iterators for memory efficiency with large datasets
- Prefer `itertools` functions over manual iteration logic
- Use `functools.lru_cache` or `functools.cache` for memoization
- Profile before optimizing, use `cProfile` or `line_profiler`
- Avoid premature optimization, prioritize readability first
