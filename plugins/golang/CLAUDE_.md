# Go Coding Guidelines

## Code Style & Formatting

- Run `gofmt` or `goimports` on all code (enforced automatically)
- Follow Effective Go conventions for naming, structure, and idioms
- Use short, clear names: prefer `i` over `index`, `buf` over `buffer` in limited scopes
- Acronyms should be consistent case: `HTTPServer`, `userID`, not `HttpServer`, `userId`
- Document exported identifiers with comments starting with the identifier name

## Package Organization

- Keep packages focused on single responsibility, avoid "util" or "common" packages
- Use internal/ directory for unexported packages shared across the module
- Name packages after what they provide, not what they contain (prefer `http` over `httputils`)
- Import paths should reflect package purpose, organize by domain not technical layer
- Avoid cyclic dependencies, refactor to break cycles with interfaces

## Error Handling

- Always check errors: never ignore returned errors, use `_` explicitly if intentional
- Use `fmt.Errorf("context: %w", err)` to wrap errors with context, preserve error chain
- Use `errors.Is(err, target)` and `errors.As(err, &target)` for error inspection
- Create sentinel errors with `var ErrNotFound = errors.New("not found")`
- Return errors as last return value, use named result parameters sparingly
- Panic only for truly unrecoverable situations, not for expected error conditions

## Interfaces & Types

- Define interfaces where they are consumed, not where types are implemented
- Keep interfaces small (often single-method), compose larger interfaces from smaller ones
- Accept interfaces, return structs (unless returning interface is part of the contract)
- Use `io.Reader`, `io.Writer`, `fmt.Stringer` and standard library interfaces
- Embed interfaces for composition: `type ReadWriter interface { Reader; Writer }`
- Use struct embedding for composition, not inheritance

## Concurrency & Goroutines

- Use goroutines for concurrent operations: `go func() { ... }()`
- Communicate via channels: `ch := make(chan T)`, prefer channels over shared memory
- Use `context.Context` for cancellation, deadlines, and request-scoped values
- Close channels from sender side, never receiver; use `defer close(ch)` pattern
- Use `sync.WaitGroup` to wait for goroutine completion, `sync.Once` for initialization
- Protect shared state with `sync.Mutex` or `sync.RWMutex` when channels aren't suitable
- Avoid goroutine leaks: ensure goroutines can exit when context is cancelled

## Context Propagation

- Pass `context.Context` as first parameter: `func DoWork(ctx context.Context, ...)`
- Never store context in structs, always pass explicitly
- Use `context.WithTimeout`, `context.WithCancel`, `context.WithDeadline` for lifecycle
- Check `ctx.Done()` in long-running operations, return `ctx.Err()` on cancellation
- Use `context.WithValue` sparingly, only for request-scoped data (e.g., trace IDs)

## Testing

- Write tests in `_test.go` files, use `*_test` package for black-box testing
- Use table-driven tests with `t.Run()` for multiple test cases
- Example:
  ```go
  tests := []struct {
      name string
      input int
      want int
  }{
      {"zero", 0, 0},
      {"positive", 5, 25},
  }
  for _, tt := range tests {
      t.Run(tt.name, func(t *testing.T) {
          got := Square(tt.input)
          if got != tt.want {
              t.Errorf("got %d, want %d", got, tt.want)
          }
      })
  }
  ```
- Use `t.Helper()` in test helper functions to improve error location reporting
- Use `testing.Short()` to skip long-running tests: `if testing.Short() { t.Skip() }`
- Prefer standard library `testing` package, use `testify` for assertions if desired

## Pointers & Values

- Use pointers for large structs, mutable state, or when nil is meaningful
- Return values for small structs (< 64 bytes) and immutable data
- Receiver methods: use pointer receivers for mutation, value receivers for read-only
- Be consistent with receiver type across all methods of a type
- Use `new(T)` for zero-initialized pointer, `&T{}` for composite literals

## Best Practices

- Prefer composition over inheritance, use struct embedding and interfaces
- Use `defer` for cleanup, placed immediately after resource acquisition
- Initialize maps before use: `m := make(map[K]V)`, check existence: `val, ok := m[key]`
- Use `for range` to iterate slices/maps, receive index/key and value
- Avoid naked returns except in very short functions (< 10 lines)
- Use constants for magic numbers and strings: `const MaxRetries = 3`
- Prefer standard library over third-party dependencies when possible

## Common Patterns

- Options pattern for configuration:
  ```go
  type Option func(*Config)
  func WithTimeout(d time.Duration) Option {
      return func(c *Config) { c.Timeout = d }
  }
  ```
- Functional options for variadic configuration
- Builder pattern for complex struct initialization
- Use `sync.Pool` for frequently allocated/deallocated objects
- Worker pools with channels for bounded concurrency

## Tooling & Quality

- Run `go vet` to catch common mistakes, `staticcheck` for deeper analysis
- Use `golangci-lint` with multiple linters enabled in CI
- Run `go mod tidy` to clean dependencies, `go mod vendor` for vendoring
- Use `go generate` for code generation, document with `//go:generate` comments
- Profile with `pprof`: `import _ "net/http/pprof"` for profiling endpoints

## Performance

- Use `strings.Builder` for string concatenation in loops, not `+` operator
- Pre-allocate slices when size is known: `make([]T, 0, capacity)`
- Use `sync.Pool` for temporary object reuse to reduce GC pressure
- Benchmark with `go test -bench=.`, profile before optimizing
- Avoid premature optimization, measure first with benchmarks and profiling
