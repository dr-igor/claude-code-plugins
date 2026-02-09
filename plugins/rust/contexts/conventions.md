# Rust Coding Conventions

## Clean Code Examples

### Declarative Code

```rust
// ✓ Use Declarative
fn get_active_user_emails(users: &[User]) -> Vec<String> {
    users
        .iter()
        .filter(|user| user.is_active)
        .map(|user| user.email.to_lowercase())
        .collect()
}

// ✗ Avoid Imperative
fn get_active_user_emails(users: &[User]) -> Vec<String> {
    let mut emails = Vec::new();
    for user in users {
        if user.is_active {
            emails.push(user.email.to_lowercase());
        }
    }
    emails
}
```

### Resource Cleanup

```rust
// ✓ Use RAII - Drop trait ensures cleanup

fn process_file(filename: &str) -> Result<String, Error> {
    let mut file = File::open(filename)?;
    let mut data = String::new();
    file.read_to_string(&mut data)?;
    Ok(transform(&data))
    // File automatically closed by implementation of `drop` when it goes out of scope
}

// Custom RAII guard
struct TransactionGuard<'a> {
    conn: &'a mut Connection,
    committed: bool,
}

impl<'a> TransactionGuard<'a> {
    fn new(conn: &'a mut Connection) -> Result<Self, Error> {
        conn.execute("BEGIN")?;
        Ok(Self { conn, committed: false })
    }

    fn commit(mut self) -> Result<(), Error> {
        self.conn.execute("COMMIT")?;
        self.committed = true;
        Ok(())
    }
}

impl<'a> Drop for TransactionGuard<'a> {
    fn drop(&mut self) {
        if !self.committed {
            let _ = self.conn.execute("ROLLBACK");
        }
    }
}
```
