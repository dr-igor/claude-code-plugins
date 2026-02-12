# Advanced Go Software Engineering Conventions

## Convention Examples

### Behavioral Testing

```go
// ✓ Use behavioral tests
func TestUserManager_RetrievesStoredUsers(t *testing.T) {
    manager := NewUserManager()
    user := User{ID: 1, Name: "Alice"}

    manager.AddUser(user)
    retrieved, err := manager.GetUser(1)

    require.NoError(t, err)
    assert.Equal(t, "Alice", retrieved.Name)
}

// ✗ Avoid structural tests
func TestUserManager_InternalState(t *testing.T) {
    manager := NewUserManager()
    assert.NotNil(t, manager.users)
    assert.IsType(t, map[int]User{}, manager.users)
}
```

### Discriminating Types at Ingestion and Wrapping Errors

This section provides an example demonstrating how to discriminate input data into known types at ingestion time, and wrap errors for unknown types instead of raising exceptions immediately.

```go
type ShapeKind string

const (
    ShapeCircle    ShapeKind = "circle"
    ShapeRectangle ShapeKind = "rectangle"
)

type Shape interface {
    Area() (float64, error)
}

type Circle struct {
    Radius float64 `json:"radius"`
}

func (c Circle) Area() (float64, error) {
    return math.Pi * c.Radius * c.Radius, nil
}

type Rectangle struct {
    Width  float64 `json:"width"`
    Height float64 `json:"height"`
}

func (r Rectangle) Area() (float64, error) {
    return r.Width * r.Height, nil
}

type ErrorShape struct {
    InputData json.RawMessage
    Err       error
}

func (e ErrorShape) Area() (float64, error) {
    return 0, fmt.Errorf("cannot compute area for unknown shape %s: %w", e.InputData, e.Err)
}

func ParseShapesFromAPI(rawData []json.RawMessage) []Shape {
    shapes := make([]Shape, 0, len(rawData))
    for _, raw := range rawData {
        shape, err := parseShape(raw)
        if err != nil {
            shapes = append(shapes, ErrorShape{InputData: raw, Err: err})
            continue
        }
        shapes = append(shapes, shape)
    }
    return shapes
}

func parseShape(raw json.RawMessage) (Shape, error) {
    var header struct {
        Type ShapeKind `json:"type"`
    }
    if err := json.Unmarshal(raw, &header); err != nil {
        return nil, fmt.Errorf("unmarshal shape header: %w", err)
    }

    switch header.Type {
    case ShapeCircle:
        var c Circle
        if err := json.Unmarshal(raw, &c); err != nil {
            return nil, fmt.Errorf("unmarshal circle: %w", err)
        }
        return c, nil
    case ShapeRectangle:
        var r Rectangle
        if err := json.Unmarshal(raw, &r); err != nil {
            return nil, fmt.Errorf("unmarshal rectangle: %w", err)
        }
        return r, nil
    default:
        return nil, fmt.Errorf("unknown shape type: %q", header.Type)
    }
}
```

### Encapsulate External Resources in Clients

```go
type ConfigurationClient interface {
    FetchConfig(ctx context.Context, key string) (map[string]any, error)
}

type FileConfigClient struct {
    configPath string
}

func NewFileConfigClient(configPath string) *FileConfigClient {
    return &FileConfigClient{configPath: configPath}
}

func (c *FileConfigClient) FetchConfig(ctx context.Context, key string) (map[string]any, error) {
    // Actual file I/O
    ...
}

type MockConfigClient struct {
    MockData map[string]map[string]any
}

func (m *MockConfigClient) FetchConfig(_ context.Context, key string) (map[string]any, error) {
    data, ok := m.MockData[key]
    if !ok {
        return nil, fmt.Errorf("config key not found: %s", key)
    }
    return data, nil
}
```
