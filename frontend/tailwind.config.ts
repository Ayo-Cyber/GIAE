import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0a0a14",
          surface: "#0f0f1e",
          elevated: "#13131f",
        },
        brand: {
          DEFAULT: "#6366f1",
          hover: "#818cf8",
          muted: "rgba(99,102,241,0.15)",
          border: "rgba(99,102,241,0.25)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
      backgroundImage: {
        "radial-indigo":
          "radial-gradient(circle at 20% 50%, rgba(99,102,241,0.06) 0%, transparent 60%)",
        "radial-emerald":
          "radial-gradient(circle at 80% 20%, rgba(16,185,129,0.04) 0%, transparent 60%)",
        "grid-pattern":
          "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "40px 40px",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-up": "fadeUp 0.5s ease forwards",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        glowPulse: {
          "0%, 100%": { boxShadow: "0 0 20px rgba(99,102,241,0.1)" },
          "50%": { boxShadow: "0 0 40px rgba(99,102,241,0.25)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
