import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Vitest runs against the same path aliases as Next.js.
 *
 * `@vitejs/plugin-react` is deliberately not used -- it currently conflicts on
 * peer dependencies with the Babel version this project resolves. Vite's own
 * transform handles TSX with React 19's automatic JSX runtime, which is all
 * these tests need.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
    restoreMocks: true,
  },
});
