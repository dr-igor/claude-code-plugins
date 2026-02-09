# Advanced TypeScript Software Engineering Conventions

## Convention Examples

### Behavioral Testing

```typescript
// ✓ Use behavioral test
it("should calculate correct total for multiple items", () => {
  const cart = new ShoppingCart();
  cart.addItem({ name: "Book", price: 20 });
  cart.addItem({ name: "Pen", price: 5 });

  expect(cart.getTotal()).toBe(25);
});

// ✗ Avoid structural test
it("should have empty items array", () => {
  const cart = new ShoppingCart();
  expect((cart as any).items).toEqual([]);
});
```

### Discriminating Types at Ingestion and Wrapping Errors

This section provides and example demonstrating how to discriminate input data into known types at ingestion time, and wrap errors for unknown types instead of raising exceptions immediately.

```typescript
type CircleData = { type: "circle"; radius: number };
type RectangleData = { type: "rectangle"; width: number; height: number };
type ShapeData = CircleData | RectangleData;

function isCircleData(shape: ShapeData): shape is CircleData {
  return shape.type === "circle";
}

function isRectangleData(shape: ShapeData): shape is RectangleData {
  return shape.type === "rectangle";
}

function parseShapesFromApi(rawData: unknown[]): ShapeData[] {
  return rawData.map((item) => {
    const shape = item as { type: string };
    if (isCircleData(shape)) {
      return new Circle(shape);
    } else if (isRectangleData(shape)) {
      return new Rectangle(shape);
    } else {
      return new ErrorShape(
        shape,
        new Error(`Unknown shape type: ${shape.type}`),
      );
    }
  });
}

class Circle {
  constructor(private data: CircleData) {}

  area(): number {
    return Math.PI * this.data.radius ** 2;
  }
}

class Rectangle {
  constructor(private data: RectangleData) {}

  area(): number {
    return this.data.width * this.data.height;
  }
}

class ErrorShape {
  constructor(
    private inputData: unknown,
    private error: Error,
  ) {}

  area(): never {
    throw new Error(
      `Cannot compute area for unknown shape: ${JSON.stringify(this.inputData)}. Original error: ${this.error.message}`,
    );
  }
}
```
