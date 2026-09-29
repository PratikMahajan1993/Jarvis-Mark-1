import { FlatCompat } from "@eslint/eslintrc";
import { fileURLToPath } from "node:url";
import path from "node:path";

const baseDirectory = path.dirname(fileURLToPath(import.meta.url));
const compat = new FlatCompat({ baseDirectory });

const FEATURE_BLOCKED = [
  { group: ["@/core", "@/core/*"], message: "Features import only from @/sdk." },
  { group: ["@/substrate", "@/substrate/*"], message: "Features never touch the substrate. Use useOrb() from @/sdk." },
  { group: ["@/lib", "@/lib/*"], message: "Features import only from @/sdk (api, hooks)." },
  { group: ["@/components/orchestrator/*", "@/components/pane/*"], message: "Core components are not a feature API." },
  { group: ["lenis", "lenis/*"], message: "Features never own scroll. Use useSection() from @/sdk." },
  { group: ["ogl", "three", "three/*"], message: "Exactly one WebGL context lives in the substrate." },
];

const config = [
  {
    ignores: [".next/**", "next-env.d.ts", "node_modules/**", "public/**", "src/lib/api/schema.gen.ts"],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    files: ["src/features/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": ["error", { patterns: FEATURE_BLOCKED }],
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name='requestAnimationFrame']",
          message: "Features never start their own rAF loop.",
        },
        {
          selector:
            "CallExpression[callee.property.name='addEventListener'][arguments.0.value=/^(scroll|wheel)$/]",
          message: "Features never listen to page scroll. Use useSection() from @/sdk.",
        },
        {
          selector: "CallExpression[callee.property.name='getContext']",
          message: "Features never create a canvas context.",
        },
      ],
    },
  },
];

export default config;
