# Command runner guidelines

- Always prefer `just` over make, except for actual C/C++ builds
- Never create a `Makefile` - create a `justfile` instead; _do_ use and update the `Makefile` if one already exists
