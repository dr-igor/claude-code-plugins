# Advanced Rust Software Engineering Conventions

## Convention Examples

### Discriminating Types at Ingestion

```rust
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
enum ShapeData {
    Circle { radius: f64 },
    Rectangle { width: f64, height: f64 },
}

// Discriminated immediately during deserialization
fn parse_shapes_from_api(json: &str) -> Result<Vec<ShapeData>, serde_json::Error> {
    serde_json::from_str(json)
}

// Type-specific logic
impl ShapeData {
    fn area(&self) -> f64 {
        match self {
            ShapeData::Circle { radius } => std::f64::consts::PI * radius * radius,
            ShapeData::Rectangle { width, height } => width * height,
        }
    }
}
```
