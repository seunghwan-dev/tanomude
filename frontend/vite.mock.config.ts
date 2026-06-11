import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import autoprefixer from "autoprefixer";
import tailwindcss from "tailwindcss";
import { defineConfig } from "vite";

import baseTailwind from "./tailwind.config";

const fromHere = (relative: string): string => fileURLToPath(new URL(relative, import.meta.url));

export default defineConfig({
  plugins: [react()],
  root: fromHere("./mock"),
  base: "/tanomude/",
  resolve: {
    alias: [
      { find: "./useAgentStream", replacement: fromHere("./mock/useAgentStreamMock.ts") },
      { find: "./api", replacement: fromHere("./mock/apiMock.ts") },
      { find: "../api", replacement: fromHere("./mock/apiMock.ts") },
    ],
  },
  css: {
    postcss: {
      plugins: [
        tailwindcss({ ...baseTailwind, content: ["./src/**/*.{ts,tsx}", "./mock/**/*.{ts,tsx,html}"] }),
        autoprefixer(),
      ],
    },
  },
  build: {
    outDir: fromHere("./dist-mock"),
    emptyOutDir: true,
  },
});
