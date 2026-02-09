# Rust Coding Guidelines

## Ownership & Borrowing

- Prefer borrowing (`&T`) over cloning unless ownership transfer is needed
- Use `&mut T` for mutable borrows, minimize mutable state
- Use `Cow<'a, T>` for conditional ownership (borrow when possible, own when necessary)
- Avoid `Rc<RefCell<T>>` unless shared mutable state is unavoidable; prefer message passing
- Use lifetimes explicitly when elision rules don't apply, keep them minimal

## Type System & Patterns

- Use enums for state machines and discriminated unions, not inheritance
- Derive common traits: `#[derive(Debug, Clone, PartialEq, Eq)]`
- Use newtype pattern (`struct UserId(u64)`) for type safety and domain modeling
- Prefer `Option<T>` over null-like sentinels, `Result<T, E>` over exceptions
- Use tuple structs for simple wrappers, full structs for named fields
- Implement `From`/`Into` for conversions, `TryFrom`/`TryInto` for fallible conversions

## Error Handling

- Use `thiserror` for library errors (derive Error), `anyhow` for application errors
- Always use `?` operator for error propagation, avoid `.unwrap()` in production code
- Use `.expect("reason")` over `.unwrap()` to document invariants
- Create custom error types with meaningful variants for domain errors
- Return `Result<T, E>` from fallible functions, never panic in library code

## Async & Concurrency

- Use `tokio` runtime for async applications, `async-std` as alternative
- Prefer message passing with channels over shared state (`tokio::sync::mpsc`)
- Use `Arc<Mutex<T>>` or `Arc<RwLock<T>>` sparingly, only for shared mutable state
- Use `tokio::select!` for concurrent operations with cancellation
- Avoid `.await` in loops, use `futures::stream` or `tokio::task::JoinSet` instead
- Use `tokio::spawn` for independent tasks, structured concurrency for dependent work

## Iterators & Functional Patterns

- Prefer iterators over loops: `.map()`, `.filter()`, `.fold()`, `.collect()`
- Use `.iter()` for borrowed iteration, `.into_iter()` for consuming iteration
- Chain iterator methods instead of intermediate collections
- Use `.filter_map()` for simultaneous filtering and mapping
- Leverage `Iterator::sum()`, `::product()`, `::min()`, `::max()` for aggregations

## Code Organization

- Keep modules focused: one file per major type or feature
- Use `pub(crate)` for internal APIs, minimize public surface area
- Organize with `mod.rs` or inline modules, prefer flat structures
- Use workspaces for multi-crate projects in single repository
- Follow naming conventions: snake_case for functions/modules, PascalCase for types

## Pattern Matching

- Use `match` exhaustively, prefer it over if-let chains (or use `let-else`)
- Use `if let` for single-pattern matching, `while let` for loops
- Use `@` bindings to name matched values: `Some(val @ 10..=20) =>`
- Use `_` for unused variables, `..` for ignored fields/ranges
- Leverage match guards for additional conditions: `Some(x) if x > 0 =>`

## Testing

- Write unit tests with `#[cfg(test)]` modules in same file
- Write integration tests in `tests/` directory for public API testing
- Use `#[should_panic]` for tests expecting panics, with `expected` message
- Use property-based testing with `proptest` or `quickcheck` for edge cases
- Mock with traits and dependency injection, or use `mockall` crate
- Use `cargo test -- --nocapture` to see println output during tests

## Performance & Best Practices

- Use `String` for owned strings, `&str` for borrowed, `Cow<str>` for conditional ownership
- Pre-allocate with `.with_capacity()` when size is known for `Vec`, `HashMap`, etc.
- Use `Box<[T]>` for fixed-size slices, `Vec<T>` for growable arrays
- Profile with `cargo flamegraph` or `perf`, benchmark with `criterion`
- Avoid premature optimization, use `#[inline]` sparingly based on profiling
- Use `cargo clippy` for lints, `cargo fmt` for formatting

## Cargo & Tooling

- Pin dependencies with `=` for applications, use semver ranges for libraries
- Use feature flags to make dependencies optional: `[features]` in Cargo.toml
- Run `cargo clippy -- -D warnings` in CI to enforce lint rules
- Use `cargo nextest` for faster test execution
- Consider `cargo-expand` for macro debugging, `cargo-audit` for security

## Safety & FFI

- Minimize `unsafe` code, document invariants with SAFETY comments
- Use `#[repr(C)]` for FFI types, ensure proper layout and alignment
- Validate all invariants at `unsafe` boundaries, never trust external code
- Consider `#[forbid(unsafe_code)]` for libraries that shouldn't use unsafe
- Use `std::ptr::NonNull` over raw pointers when pointer is never null
