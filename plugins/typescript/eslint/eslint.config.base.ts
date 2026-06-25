import tseslint from "typescript-eslint";
import promise from "eslint-plugin-promise";
import unicorn from "eslint-plugin-unicorn";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  tseslint.configs.recommendedTypeChecked,
  {
    plugins: { promise, unicorn },
    rules: {
      // --- Strict typing ---
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-assertions": [
        "error",
        { assertionStyle: "never" },
      ],
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/switch-exhaustiveness-check": "error",

      "promise/prefer-await-to-then": "error",
      "@typescript-eslint/no-floating-promises": [
        "error",
        { ignoreVoid: true },
      ],
      "@typescript-eslint/no-misused-promises": "error",

      "unicorn/no-for-loop": "error",
      "unicorn/no-array-for-each": "error",
      "unicorn/prefer-array-some": "error",
      "unicorn/prefer-array-find": "error",

      "unicorn/no-process-exit": "error",

      "max-lines-per-function": [
        "error",
        { max: 50, skipBlankLines: true, skipComments: true },
      ],
      "max-params": ["error", { max: 3 }],
      complexity: ["warn", 10],
      "max-depth": ["warn", 3],
      "max-nested-callbacks": ["warn", 3],

      "prefer-const": "error",
      "no-param-reassign": ["error", { props: true }],
      "@typescript-eslint/prefer-readonly": "error",

      "@typescript-eslint/naming-convention": [
        "error",
        {
          selector: "variable",
          types: ["boolean"],
          format: ["PascalCase"],
          prefix: ["is", "has", "should", "can", "did", "will"],
        },
      ],
    },
  },
  {
    files: ["**/*.{test,spec}.ts"],
    rules: { "max-lines-per-function": "off" },
  },
  prettier,
);
