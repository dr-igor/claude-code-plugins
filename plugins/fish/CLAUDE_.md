# Fish Shell Scripting Guidelines

## Fish Shell Fundamentals

- Fish is **not POSIX-compliant**, do not use bash/zsh syntax
- No semicolons to separate commands, use newlines
- Use `end` to close blocks (`if`, `for`, `while`, `function`, `begin`, `switch`)
- Comments start with `#`, continue to end of line
- No subshells with `$(...)`, use `(...)` for command substitution
- No `&&` or `||` operators, use `and` / `or` keywords instead

## Variables

- Set variables with `set`: `set var_name value`
- Variable scopes: `-l` (local), `-g` (global), `-U` (universal), `-x` (export)
- Prefer local scope by default: `set -l my_var "value"`
- Universal variables persist across sessions: `set -U fish_greeting ""`
- Export for environment variables: `set -x PATH /usr/local/bin $PATH`
- Access variables with `$var_name` or `$var_name[index]` for list elements
- Query variables: `set -q var_name` returns 0 if variable exists
- Erase variables: `set -e var_name`

## Lists (Arrays)

- Fish variables are lists by default: `set my_list item1 item2 item3`
- Access elements with 1-based indexing: `$my_list[1]`, `$my_list[2..-1]` (slice)
- Negative indices count from end: `$my_list[-1]` is last element
- Append to list: `set -a my_list new_item`
- Prepend to list: `set -p my_list new_item`
- Get list length: `count $my_list`
- Test if empty: `test -z "$my_list"` or `test (count $my_list) -eq 0`

## Conditionals

- Use `if`, `else if`, `else`, `end` blocks:
  ```fish
  if test $status -eq 0
      echo "Success"
  else if test $status -eq 1
      echo "Failure"
  else
      echo "Unknown"
  end
  ```
- Use `test` or `[` for conditions: `test -f file.txt`, `[ -d /path ]`
- Common tests: `-f` (file), `-d` (dir), `-e` (exists), `-z` (empty), `-n` (not empty)
- String comparison: `test "$a" = "$b"`, numeric: `test $a -eq $b`
- Combine conditions: `test -f file.txt -a -r file.txt` (`-a` for AND, `-o` for OR)
- Use `and`/`or` keywords: `command1; and command2`, `command1; or command2`

## Loops

- For loops:
  ```fish
  for item in $my_list
      echo $item
  end
  ```
- For loop with range: `for i in (seq 1 10)`
- While loops:
  ```fish
  while test $count -lt 10
      echo $count
      set count (math $count + 1)
  end
  ```
- Break and continue work as expected

## Switch Statements

```fish
switch $variable
    case value1
        echo "Matched value1"
    case value2 value3
        echo "Matched value2 or value3"
    case '*'
        echo "Default case"
end
```

## Functions

- Define functions with `function` keyword:
  ```fish
  function my_function
      echo "Arguments: $argv"
      echo "First arg: $argv[1]"
  end
  ```
- Function arguments are in `$argv` list
- Return status with `return`: `return 1` for error, `return 0` for success
- Use `--description` for help text: `function my_func --description "Does something"`
- Use `--argument-names` for named parameters: `function greet --argument-names name`
- Save functions to file in `~/.config/fish/functions/` for autoloading

## Argument Parsing

- Use `argparse` for robust option parsing:
  ```fish
  function my_command
      argparse 'h/help' 'v/verbose' 'o/output=' -- $argv
      or return 1

      if set -q _flag_help
          echo "Usage: my_command [OPTIONS]"
          return 0
      end

      set -q _flag_verbose; and set verbose true
      set output_file $_flag_output
  end
  ```
- Short options: `'v/verbose'`, long options: `'verbose'`, with values: `'o/output='`
- Required arguments come after `--`: remaining in `$argv`

## String Operations

- Use `string` command for all string operations
- Substring: `string sub --start 1 --length 5 $str`
- Split: `string split ',' $str` returns list
- Join: `string join ',' $list`
- Replace: `string replace 'old' 'new' $str`
- Match (grep-like): `string match '*pattern*' $str`
- Trim: `string trim $str`, `string trim --chars='/' $str`
- Case conversion: `string lower $str`, `string upper $str`
- Length: `string length $str`

## Command Substitution

- Use parentheses for command substitution: `set output (command)`
- Capture lines as list elements: `set lines (cat file.txt)`
- Use `(command | string collect)` to preserve newlines as single string
- Status of last command: `$status` (0 for success, non-zero for error)
- Use `command; or return` pattern to exit function on command failure

## Path Management

- Add to PATH: `fish_add_path /usr/local/bin` (automatic deduplication)
- Prepend to PATH: `fish_add_path --prepend ~/.local/bin`
- PATH is a global exported list variable: `set -gx PATH /new/path $PATH`
- Check if command exists: `type -q command_name`

## Completions

- Define completions in `~/.config/fish/completions/` as `command.fish`
- Basic completion: `complete -c mycommand -a "arg1 arg2 arg3"`
- Option completion: `complete -c mycommand -s o -l option --description "Description"`
- Dynamic completions with functions:
  ```fish
  complete -c mycommand -a "(my_completion_function)"
  ```
- Conditional completions: `complete -c git -n "__fish_seen_subcommand_from commit" -a ...`

## Abbreviations

- Use `abbr` for expanding shortcuts (preferred over alias):
  ```fish
  abbr -a gs "git status"
  abbr -a gco "git checkout"
  ```
- Abbreviations expand in command line before execution
- Universal abbreviations: `abbr -a -U gs "git status"` (persist across sessions)
- List: `abbr --list`, erase: `abbr --erase name`

## Environment & Configuration

- Config file: `~/.config/fish/config.fish` (runs on every shell start)
- Interactive-only config: wrap in `status is-interactive; and ...`
- Function definitions go in `~/.config/fish/functions/` for autoloading
- Completions go in `~/.config/fish/completions/`
- Check if running as login shell: `status is-login`

## Best Practices

- Quote variables when whitespace/empty values matter: `"$var"`
- Prefer `test` over `[` for readability (they are equivalent)
- Use `type -q` to check if command exists before using it
- Use `set -l` for local variables in functions to avoid polluting scope
- Return meaningful exit codes: `return 0` for success, non-zero for errors
- Use `begin; ...; end` to group commands and control variable scope
- Prefer `string` command over `sed`, `awk`, `cut` for string operations
- Use `math` for arithmetic: `set result (math "$a + $b")`

## Common Patterns

- Check if file exists and is readable:
  ```fish
  if test -f file.txt -a -r file.txt
      # process file
  end
  ```
- Loop over command output:
  ```fish
  for line in (cat file.txt)
      echo $line
  end
  ```
- Default value for variable:
  ```fish
  set -q my_var; or set my_var "default"
  ```
- Exit on error pattern:
  ```fish
  some_command
  or return $status
  ```

## Differences from Bash/Zsh

- No `$()` for command substitution, use `()`
- No `export VAR=value`, use `set -x VAR value`
- No `&&`/`||`, use `and`/`or` keywords
- No `${var}` expansion syntax (except `${var}` for preventing parsing issues)
- Arrays are 1-indexed, not 0-indexed
- Use `status` instead of `$?` for last command exit code
- Use `string` command instead of bash string manipulation `${var/pattern/replacement}`
