import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#12211b",
          900: "#1b2d26",
          700: "#3f544b",
          500: "#6b7d75",
        },
        cream: {
          50: "#fbfaf5",
          100: "#f5f2e9",
          200: "#eae5d6",
        },
        jade: {
          900: "#0f513f",
          700: "#17755b",
          600: "#208a69",
          500: "#2a9f79",
          100: "#ddf1e8",
          50: "#eff9f4",
        },
        amber: {
          600: "#b87420",
          100: "#f7ead3",
          50: "#fdf6e9",
        },
      },
      fontFamily: {
        sans: [
          "var(--font-sans)",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        display: [
          "var(--font-display)",
          "Georgia",
          "ui-serif",
          "serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        lift: "0 1px 2px rgba(18,33,27,.05), 0 14px 40px rgba(18,33,27,.08)",
        card: "0 1px 1px rgba(18,33,27,.04), 0 6px 20px rgba(18,33,27,.05)",
      },
      animation: {
        "fade-up": "fade-up .4s cubic-bezier(.22,.8,.3,1) both",
        "soft-pulse": "soft-pulse 1.4s ease-in-out infinite",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "soft-pulse": {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;

