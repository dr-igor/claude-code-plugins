# TypeScript Coding Conventions

## Typing

Type safety must be a top priority, even if it makes the code more verbose. Completely typed code catches more issues sooner.

- Leverage TypeScript's latest features to ensure that types are well defined.
- Do not take shortcuts with typing, unless it is the _only_ way to solve the problem.
  - Avoid explicit casting; if you find yourself using `as` or `satisfies`, consider if there is a more type-safe way to achieve the same result, even if more verbose.
    - Assume the function is generic and try type specification first (e.g. `getContext<ExpectedType>()` instead of `getContext() as ExpectedType`).
- **Never** use `any`.

## Clean Code Examples

### Declarative Code

```typescript
// ✓ Use Declarative
function getActiveUserEmails(users: User[]): string[] {
  return users
    .filter((user) => user.isActive)
    .map((user) => user.email.toLowerCase());
}

// ✗ Avoid Imperative
function getActiveUserEmails(users: User[]): string[] {
  const emails: string[] = [];
  for (let i = 0; i < users.length; i++) {
    if (users[i].isActive) {
      emails.push(users[i].email.toLowerCase());
    }
  }
  return emails;
}
```

### Resource Cleanup

```typescript
// ✓ Use try/finally for Resource Cleanup
function processFile(filename: string): string {
  const file = openFile(filename);
  try {
    const data = file.read();
    return transform(data);
  } finally {
    file.close();
  }
}

// ✗ Avoid Manual Cleanup
function processFile(filename: string): string {
  const file = openFile(filename);
  const data = file.read();
  file.close();
  return transform(data);
}
```

### Prefer `await`/`void` Over `.then()` Chains

```typescript
// ✓ Use `await` and `void`
void (async function fetchAndProcess() {
  // Note explicit `void` to indicate we are intentionally not awaiting
  const data = await fetchData();
  const processed_data = await processData(data);
  void doMoreProcessing(processed_data);
})();

doOtherWork();

// ✗ Avoid `.then()` Chains
fetchData().then((data) => {
  processData(data).then((processed_data) => {
    doMoreProcessing(processed_data);
  });
});

doOtherWork();
```
