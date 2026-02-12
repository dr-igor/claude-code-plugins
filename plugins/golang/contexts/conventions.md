# Go Coding Conventions

## Version

- Check project files for Go version in use (e.g., `go.mod`).
- If none found, target Go 1.22+.

## Dependency Management

Use Go modules (`go.mod` / `go.sum`) for dependency management.

## Go-Specific Requirements

- Use `errors.New` or `fmt.Errorf` with `%w` for error wrapping; avoid bare string errors.
- Use struct types and named fields for structured data; avoid `map[string]interface{}` when the shape is known.
- Use `context.Context` as the first parameter of functions that perform I/O or long-running operations.
- Prefer table-driven tests.
- Use `t.Helper()` in test helper functions.
- Use `io.Reader` and `io.Writer` interfaces for streaming data; avoid loading entire files into memory when streaming is feasible.

## Typing

- Use strong typing; avoid `interface{}` / `any` unless genuinely polymorphic.
- Define concrete types and interfaces at the point of use.

## Error Handling

- Always check returned errors; never discard them with `_`.
- Return errors to the caller rather than logging and continuing; let the caller decide how to handle them.
- Use sentinel errors or custom error types for errors that callers need to distinguish programmatically.

## Clean Code Examples

### Declarative Code

```go
// ✓ Use higher-order patterns where idiomatic
func getActiveUserEmails(users []User) []string {
    var emails []string
    for _, user := range users {
        if user.IsActive {
            emails = append(emails, strings.ToLower(user.Email))
        }
    }
    return emails
}

// ✗ Avoid index-based iteration
func getActiveUserEmails(users []User) []string {
    emails := make([]string, 0)
    for i := 0; i < len(users); i++ {
        if users[i].IsActive {
            emails = append(emails, strings.ToLower(users[i].Email))
        }
    }
    return emails
}
```

### Resource Cleanup

```go
// ✓ Use defer for Resource Cleanup
func processFile(filename string) (string, error) {
    file, err := os.Open(filename)
    if err != nil {
        return "", err
    }
    defer file.Close()

    data, err := io.ReadAll(file)
    if err != nil {
        return "", err
    }
    return transform(string(data)), nil
}

// ✗ Avoid Manual Resource Management
func processFile(filename string) (string, error) {
    file, err := os.Open(filename)
    if err != nil {
        return "", err
    }

    data, err := io.ReadAll(file)
    if err != nil {
        return "", err // file never closed
    }
    file.Close()
    return transform(string(data)), nil
}
```

### Concurrency

```go
// ✓ Use goroutines with errgroup for concurrent work
func fetchAll(ctx context.Context, urls []string) ([]Response, error) {
    g, ctx := errgroup.WithContext(ctx)
    results := make([]Response, len(urls))

    for i, url := range urls {
        g.Go(func() error {
            resp, err := fetch(ctx, url)
            if err != nil {
                return err
            }
            results[i] = resp
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}

// ✗ Avoid sequential fetching when requests are independent
func fetchAll(ctx context.Context, urls []string) ([]Response, error) {
    var results []Response
    for _, url := range urls {
        resp, err := fetch(ctx, url)
        if err != nil {
            return nil, err
        }
        results = append(results, resp)
    }
    return results, nil
}
```

## Frameworks and Libraries

- Use `cobra` and `viper` for CLI applications.
- Use `slog` (standard library) for structured logging.
- Use `testify` for test assertions and mocking when it simplifies test code.
