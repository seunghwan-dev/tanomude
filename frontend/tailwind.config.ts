import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: { DEFAULT: "#F4F1EA", panel: "#FBFAF6", sunk: "#ECE6D8" },
        ink: { DEFAULT: "#1C1A17", soft: "#4A463F", faint: "#8A8479" },
        seal: { DEFAULT: "#B23A26", deep: "#8E2C1C", wash: "#F2D9D1" },
        phosphor: { DEFAULT: "#1C7A45", glow: "#2FB866" },
        line: "#D9D2C3",
      },
      fontFamily: {
        sans: ['"Inter"', '"Noto Sans JP"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "inset 0 1px 0 rgba(255,255,255,0.7), 0 10px 34px -16px rgba(28,26,23,0.35)",
        seal: "inset 0 1px 0 rgba(255,255,255,0.4), 0 6px 16px -6px rgba(178,58,38,0.5)",
      },
      borderRadius: { card: "14px" },
    },
  },
  plugins: [],
} satisfies Config;
