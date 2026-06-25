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

Create type predicates for discrimination wherever possible.

### Discriminated Union Maps for Correlation

Define a single map interface where keys are discriminant strings and values define the remainder of the type. Derive concrete types via the mapped type. This allows type-safe correlation of types without needing `switch`, `as`, or `satisfies`.

```typescript
interface MessageToContentMap {
  scan: { imageUrls: string[] };
  highlight: { selector: string; color: string };
  clear: Record<string, never>;
}

type MessageToContent<K extends keyof MessageToContentMap> = {
  type: K;
} & MessageToContentMap[K];

type ScanMessage = MessageToContent<"scan">;
type HighlightMessage = MessageToContent<"highlight">;
type ClearMessage = MessageToContent<"clear">;

type ResponseMessageMap = {
  scan: { success: boolean; scannedCount: number };
  highlight: { success: boolean };
  clear: { success: boolean };
};

type ContentHandler<K extends keyof MessageToContentMap, R = void> = (
  msg: MessageToContent<K>,
  sendResponse: (response: ResponseMessageMap[K]) => void,
) => R;

const handlers: {
  [K in keyof MessageToContentMap]: ContentHandler<K>;
} = {
  scan: (msg, sendResponse) => {
    /* msg is ScanMessage */
  },
  highlight: (msg, sendResponse) => {
    /* msg is HighlightMessage */
  },
  clear: (msg, sendResponse) => {
    /* msg is ClearMessage */
  },
};

function dispatch<K extends keyof MessageToContentMap>(
  key: K,
  message: MessageToContent<K>,
  sendResponse: (response: ResponseMessageMap[K]) => void,
): void {
  handlers[key](message, sendResponse);
}

browser.runtime.onMessage.addListener<MessageToContent>(
  (message, _sender, sendResponse) => {
    dispatch(message.type, message, sendResponse);
    return true;
  },
);
```

### Generic API Wrappers

Add type parameters to API type definitions to allow callers to specify the expected return type, instead of forcing them to use `as` casts.

```typescript
// ✓ Generic wrapper — caller controls the return type
// chrome.d.ts
declare namespace chrome {
  namespace storage {
    namespace local {
      function get<T extends Record<string, unknown>>(
        keys?: string | string[] | null,
      ): Promise<T>;
      function set<T extends Record<string, unknown>>(items: T): Promise<void>;
    }
  }
  namespace runtime {
    function sendMessage<M, T>(message: M): Promise<T>;
    namespace onMessage {
      function addListener<T, R>(
        callback: (
          message: T,
          sender: MessageSender,
          sendResponse: (response: R) => void,
        ) => boolean | void,
      ): void;
    }
  }
}

function sendMessage<M, T>(message: M): Promise<T> {
  return chrome.runtime.sendMessage<M, T>(message);
}

function addListener<T>(callback: (msg: T) => void): void {
  chrome.runtime.onMessage.addListener<T, void>(callback);
}

async function storageGet<T extends Record<string, unknown>>(
  keys: string[],
): Promise<T> {
  return chrome.storage.local.get<T>(keys);
}

// ✗ Avoid — forces `as` casts
function sendMessage<M, T>(message: M): Promise<T> {
  return chrome.runtime.sendMessage(message) as Promise<T>;
}

function addListener<T>(callback: (msg: T) => void): void {
  chrome.runtime.onMessage.addListener(
    callback as (
      message: unknown,
      sender: MessageSender,
      sendResponse: (response: unknown) => void,
    ) => boolean | void,
  );
}

async function storageGet<T extends Record<string, unknown>>(
  keys: string[],
): Promise<T> {
  return chrome.storage.local.get(keys) as Promise<T>;
}
```
