import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

const browserGlobals = {
  AbortController: "readonly",
  Blob: "readonly",
  Clipboard: "readonly",
  console: "readonly",
  document: "readonly",
  EventSource: "readonly",
  File: "readonly",
  fetch: "readonly",
  FormData: "readonly",
  HTMLInputElement: "readonly",
  localStorage: "readonly",
  navigator: "readonly",
  ReadableStream: "readonly",
  setTimeout: "readonly",
  TextDecoder: "readonly",
  URL: "readonly",
  window: "readonly"
};

export default tseslint.config(
  {
    ignores: ["coverage", "dist", "node_modules", "tsconfig.tsbuildinfo"]
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: browserGlobals,
      sourceType: "module"
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/consistent-type-imports": ["warn", { fixStyle: "inline-type-imports" }],
      "@typescript-eslint/no-explicit-any": "warn",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }]
    }
  },
  prettier
);
