# TypeScript Project Setup Rules

## TypeScript Version

- Until TS 7.1 is released and the compatible eslint is available, new projects should use TS 6.

## `package.json` Scripts

- Include scripts for
  - Building the project (e.g., `build`)
  - Running tests (e.g., `test`)
  - Linting the code (e.g., `lint`)
  - Formatting the code (e.g., `format`)
  - Type checking (e.g., `type-check`)

## Packager

- Use `vite` as the default packager for new TypeScript projects.

## Testing Framework

- Use `vitest` as the default testing framework for new TypeScript projects.

## Linter

- Use `eslint` with the `@typescript-eslint` plugin for linting TypeScript code.

## Formatter

- Use `prettier` for code formatting, integrated with `eslint` for consistent style.
  - Use a yaml configuration file (e.g., `.prettierrc.yaml`).
  - Configure the following Prettier settings:
    - `semi: false`
    - `printWidth: 88`

## Type Checking

- Use `tsc` for type checking, and set up a `tsconfig.json` with strict settings.
