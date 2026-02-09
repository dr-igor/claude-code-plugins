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
