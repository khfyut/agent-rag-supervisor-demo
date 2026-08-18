// Tailwind v3 配置：扫描 index.html 与 src 下的 ts/tsx
import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [typography],
};
