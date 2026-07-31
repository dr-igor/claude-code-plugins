# Advanced Python Software Engineering Conventions

## Convention Examples

### Behavioral Testing

```python
# ✓ Use behavioral tests
def test_user_manager_retrieves_stored_users():
    manager = UserManager()
    user = User(id=1, name="Alice")

    manager.add_user(user)
    retrieved = manager.get_user(1)

    assert retrieved.name == "Alice"

# ✗ Avoid structural test
def test_user_manager_attributes():
    manager = UserManager()
    assert hasattr(manager, '_users')
    assert isinstance(manager._users, dict)
```

### Discriminating Types at Ingestion and Wrapping Errors

This section provides and example demonstrating how to discriminate input data into known types at ingestion time, and wrap errors for unknown types instead of raising exceptions immediately.

```python
from typing import Literal
from collections.abc import Mapping
from dataclasses import dataclass

@dataclass
class Circle:
    type_: ClassVar[Literal["circle"]] = "circle"

    radius: float

    def area(self) -> float:
        return 3.14159 * self.radius ** 2

@dataclass
class Rectangle:
    type_: ClassVar[Literal["rectangle"]] = "rectangle"

    width: float
    height: float

    def area(self) -> float:
        return self.width * self.height

@dataclass
class ErrorShape:
    input_data: dict
    error: Exception

    def area(self) -> float:
        raise Exception(f"Cannot compute area for unknown shape: {self.input_data}") from self.error

class Shape(Protocol):
    def area(self) -> float:

def discriminate_shapes_from_raw(raw_data: list[Mapping]) -> list[Shape]:
    shapes = []
    for item in raw_data:
        try:
            shapes.append(mapping_to_shape(item))
        except Exception as e:
            shapes.append(ErrorShape(input_data=item, error=e))
    return shapes

def mapping_to_shape(data: Mapping) -> Shape:
    match data.pop("type"):
        case "circle":
            return Circle(**data)
        case "rectangle":
            return Rectangle(**data)
        case _:
            raise ValueError(f"Unknown shape type: {data['type']}")
```

### Encapsulate External Resources in Clients

```python
from typing import Protocol

class ConfigurationClient(Protocol):
    def fetch_config(self, key: str) -> dict: ...

class FileConfigClient:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def fetch_config(self, key: str) -> dict:
        # Actual file I/O
        ...

class MockConfigClient:
    def __init__(self, mock_data: dict):
        self.mock_data = mock_data

    def fetch_config(self, key: str) -> dict:
        return self.mock_data[key]
```

### Dimensional Quantities (Units of Measure)

When a project carries more than about 6 dimensional values — quantities with physical dimensions such as length, mass, time, temperature, or current — it shall leverage an existing, maintained units-of-measure (uom) library in which those dimensional values are defined. Tracking units in comments, variable names (`speed_m_per_s`), or bare floats is fragile and error-prone; a uom library makes dimensional mismatches (`meters + seconds`) fail instead of silently producing garbage.

- **Default: Pint.** The most complete option, the largest ecosystem, and actively maintained (BSD-3). Unit definitions live in an editable text file rather than in code; prefixed and pluralized forms parse automatically (`kilometers` follows from `kilo` + `meter`); it handles offset temperature scales correctly; and it interoperates with numpy, pandas (`pint-pandas`), xarray (`pint-xarray`), and pydantic (`pydantic-pint`).
- **Array-bound numerical code: unyt.** An `ndarray` subclass, so ufuncs stay fast. Prefer it over Pint when the workload is array-dominated and Pint's per-operation overhead is measurable.
- **Zero-overhead checking: numericalunits.** A different paradigm, not a weaker Pint: base units are defined as random positive floats, so a dimensionally-correct calculation cancels to a deterministic answer while a dimensionally-incorrect one varies across two fresh runs. Storage and compute overhead are both zero — useful for hot numerical loops where you want the check during development and nothing in production.
- **Caveat:** none of these give static, mypy-visible dimension checking. Python's type system can't express dimension arithmetic (no type-level integer exponents), so unit errors surface at runtime (or, with numericalunits, as a numerical discrepancy).
- **License flag:** avoid the PyPI package named `python-units` — it is GPL-3.0-or-later. Every option above is permissively licensed.
