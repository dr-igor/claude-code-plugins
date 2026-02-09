# TypeScript Coding Guidelines

## TypeScript Configuration

- Enable strict mode: `"strict": true` in tsconfig.json
- Use `"noUncheckedIndexedAccess": true` to catch undefined array/object access
- Enable `"exactOptionalPropertyTypes": true` to distinguish `undefined` from missing properties
- Set `"moduleResolution": "bundler"` for modern projects, `"node16"` for Node.js
- Use path aliases for cleaner imports: `@/` for src directory

## Type System

- Prefer `interface` for object shapes and public APIs, `type` for unions/intersections/utilities
- Use discriminated unions with literal types for state machines and variants
- Apply `readonly` modifiers to prevent mutation: `readonly string[]`, `Readonly<T>`
- Avoid `any` entirely; use `unknown` with type guards when type is uncertain
- Use `as const` for literal types and immutable data structures
- Define branded types with `type Brand<T, B> = T & { __brand: B }` for type safety

## Functions & Async

- Use arrow functions for inline callbacks, named functions for reusable logic
- Always use `async`/`await` syntax, never raw Promises or callbacks
- Use `Promise.all()` for concurrent operations, `Promise.allSettled()` when handling failures
- Use `Promise.race()` for timeout patterns, `AbortController` for cancellation
- Annotate async function return types explicitly: `async (): Promise<void> =>`
- Handle promise rejections with try/catch or `.catch()`

## Error Handling

- Create typed error classes extending `Error` with discriminators
- Use Result/Either types: `type Result<T, E> = { ok: true; value: T } | { ok: false; error: E }`
- Validate external data with `zod`, `io-ts`, or custom type guards
- Never throw string errors, always throw Error instances
- Use exhaustive checks with `never` for unreachable code

## Code Organization

- One export per file for focused modules, use index.ts for public API
- Co-locate types with implementation, export types explicitly
- Use barrel exports (index.ts) sparingly, prefer direct imports
- Organize by feature/domain, not by technical layer
- Keep modules small and single-responsibility

## Modern JavaScript Patterns

- Use optional chaining `?.` and nullish coalescing `??` instead of manual checks
- Prefer template literals over string concatenation
- Use destructuring for object/array extraction with meaningful names
- Use rest/spread operators for immutable updates: `{ ...obj, key: value }`
- Use `Map` and `Set` for keyed collections and unique values
- Leverage array methods: `.map()`, `.filter()`, `.reduce()`, `.find()`, `.some()`, `.every()`

## React-Specific (if applicable)

- Use functional components with hooks exclusively
- Memoize expensive computations with `useMemo`, callbacks with `useCallback`
- Define prop types with interfaces, use `React.FC` sparingly (not required)
- Extract custom hooks for reusable stateful logic
- Use `React.memo()` for performance optimization, profile first

## Testing

- Use describe/it blocks for test organization
- Test behavior and public API, not implementation details
- Use type-safe mocking with tools like `vitest` or `jest` with TypeScript
- Prefer integration tests over unit tests for business logic
- Use `expect.assertions()` to verify async test execution

## Tooling & Quality

- Use ESLint with TypeScript rules, Prettier for formatting
- Run `tsc --noEmit` in CI to verify type correctness
- Use `strict-boolean-expressions` ESLint rule to prevent implicit coercion
- Consider `tsx` for running TypeScript directly, `tsup` for bundling
- Use pnpm or yarn for package management with lockfiles

## Performance & Best Practices

- Avoid excessive type assertions (`as`), refactor types instead
- Use structural typing to advantage, avoid unnecessary inheritance
- Lazy-load modules with dynamic imports for code splitting
- Profile before optimizing, use Chrome DevTools or Node.js profiler
- Keep bundle size in check with tools like `source-map-explorer`
