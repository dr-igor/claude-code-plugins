# Fish Shell

Fish shell prioritizes consistency and discoverability over POSIX compatibility. This guide shows how to translate common bash/zsh patterns to fish.

## Common Major Incompatibilities with Bash/Zsh

### Heredocs (`<< EOF ... EOF`)

**The most common issue to run into when using `fish` shell is that it does not support heredocs (`<< EOF ... EOF` syntax).** Use multi-line strings with pipes instead (see example below).

**Bash/Zsh:**

```bash
# ✗ Avoid heredocs if the shell is `fish`
psql << EOF
SELECT *
FROM users
WHERE active = $ACTIVE;"
EOF
```

**Fish:**

```fish
# ✓ Use echo with multiline strings and pipe to command
echo "\
SELECT *
FROM users
WHERE active = $ACTIVE;" | psql
```

#### Variable Assignment and Usage

- Use `set name "value"` instead of `name="value"`.
- Use `set -l name "value"` for local variables.
- Use `set -x name "value"` to set environment variables, instead of `export name="value"`.
- For persistent environment variables, use `set -Ux name "value"`.
- Fish paths are lists, not colon-separated strings: use `set -x PATH $PATH /new/path` to append.
- Use `set value (command)` instead of `` `command` `` or `$(command)` notation.

#### Redirection

- To redirect both stdout and stderr, use the convenience operator `&>`, which works like `> [file] 2>&1`.

#### Conditional Expressions

- Use `test` or `[` without the `[[` compound command.
- No `then` keyword required.
- Close conditionals with `end` instead of `fi`

e.g.:

```fish
if test -f "$file"
    cat "$file"
else if [ -d "$file" ]  # alternative test syntax
    ls "$file"
else
    echo "not found"
end
```

#### Flow Control

- Close `for` and `while` loops with `end` instead of `done`; No `do` keyword needed.
- Use `seq` for numeric iteration instead of C-style loops:
- Use `and` and `or` keywords instead of `&&` and `||`. Separate commands with semicolons.
- Use `not` keyword instead of `!`.

```fish
for i in (seq 1 2 10)  # start, step, end; start and step are optional
    command1 $i; and command2 $i; or not command3 $i
end
```

#### Arrays and Lists

Treat all variables as lists naturally. Use 1-based indexing instead of 0-based.

e.g.:

```fish
set arr one two three
echo $arr[1]           # first element (1-indexed)
echo $arr              # all elements
echo (count $arr)      # length
set --append arr four  # append
set -a arr five        # shorthand

echo $arr[-1]       # last element: "five"
echo $arr[2..4]     # range: "two three four"
echo $arr[1 3 5]    # specific indices: "one three five"
```

#### String Manipulation

- Use the `string` command instead of parameter expansion.

e.g.:

```fish
set str "hello world"
echo (string sub --length 5 -- $str)      # substring
echo (string replace world fish -- $str)  # replace
echo (string upper -- $str)               # uppercase
echo (string length -- $str)              # length
```

#### Function Definition

- Close functions with `end` instead of braces; Use `$argv` for arguments.

e.g.:

```fish
function greet
    echo "Hello, $argv[1]"
end

# With argument description for clarity
function greet --argument name
    echo "Hello, $name"
end
```

#### Process Substitution

Use `psub` command instead of `<(command)` syntax.

**Bash/Zsh:**

```bash
diff <(command1) <(command2)
command > >(tee file)
```

**Fish:**

```fish
diff (command1 | psub) (command2 | psub)
command | tee file
```

#### Brace Expansion

Fish 3.0+ supports basic brace expansion but, empty elements in braces don't work.

e.g.:

```fish
echo {1..10}           # works in fish 3.0+
echo {a,b,c}           # works: a b c
cp file {,.bak}        # DOESN'T work ...
cp file file.bak       # ... do explicitly
mkdir -p dir/{sub1,sub2,sub3}  # works
```

#### History Substitution

Fish doesn't support `!` history syntax; use `history` array instead.

e.g.:

```fish
# $history[1] for programmatic access e.g.
eval $history[1]  # repeat last command
```

#### Subshells and Command Groups

Use `begin`/`end` blocks for command grouping.

e.g.:

```fish
(cd /tmp; and command)

begin
    command1
    command2
end > output
```

#### Arithmetic Expansion

Use `math` command instead of `$((expression))`.

e.g.:

```fish
set result (math "5 + 3")
set count (math "$count + 1")
echo (math "10 * 2")
```

#### Other Differences

- Use `source command.fish` only; dot syntax doesn't work.
- Prefer functions over aliases for proper argument handling; use `funcsave` for persistence.
