# Svelte Project Setup Rules

## Version

- Use Svelte v5 with runes.

## Format

- Use `prettier-plugin-svelte` with `svelteSortOrder: 'options-markup-scripts-styles'`

## Linting

- Use `eslint-plugin-svelte` with:

  ```javascript
  export default [
    // [...snip...]
    ...svelte.configs["flat/recommended"],
    {
      files: ["**/*.svelte"],
      languageOptions: {
        parser: svelteParser,
        parserOptions: {
          parser: tsParser,
          extraFileExtensions: [".svelte"],
          svelteFeatures: { runes: true },
        },
      },
      rules: {
        // Template markup consumes script variables; the rule can't see that usage
        "no-useless-assignment": "off",
      },
    },
  ];
  ```
