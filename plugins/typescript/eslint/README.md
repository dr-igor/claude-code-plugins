# @igor/eslint-config-typescript

Shareable ESLint flat config capturing the deterministic TypeScript conventions (strict typing, async style, declarative-over-imperative, structural limits, mutability, boolean naming). Formatter concerns are delegated to Prettier via `eslint-config-prettier`.

## Usage

In a consuming project's `eslint.config.ts`:

```typescript
import base from "@igor/eslint-config-typescript";
import tseslint from "typescript-eslint";

export default tseslint.config(...base, {
  languageOptions: {
    parserOptions: {
      projectService: true,
      tsconfigRootDir: import.meta.dirname,
    },
  },
});
```

`projectService` must be set by the consumer because it is project-relative: it points the TypeScript type checker at _this_ project's sources, which the shared package cannot know. The type-aware rules (`no-unsafe-*`, `no-floating-promises`, `prefer-readonly`, `switch-exhaustiveness-check`) require it.

## Formatting

This config does not format code. Ship a `.prettierrc.yaml` alongside it:

```yaml
semi: false
printWidth: 88
```

## Not included

Custom rules beyond `as`/`satisfies` (covered by `consistent-type-assertions: never`) — e.g. narrative-flow ordering, resource cleanup pairing — require a separate `eslint-plugin-local` and are out of scope for this base config.
