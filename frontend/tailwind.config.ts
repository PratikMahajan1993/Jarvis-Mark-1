import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#05070a",
        panel: "#0b1420",
        panel2: "#101c2c",
        cyan: "#3ee0d4",
        violet: "#a48cf2",
        magenta: "#f45fb0",
        amber: "#f5c16c",
        red: "#f2555c",
        green: "#43e0a0",
      },
      fontFamily: {
        display: ["Source Serif 4", "Iowan Old Style", "Charter", "Georgia", "serif"],
        body: ["IBM Plex Sans", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        hud: "0 0 40px rgba(62, 224, 212, 0.12)",
        "glow-cyan": "0 0 22px rgba(62, 224, 212, 0.35)",
        "glow-violet": "0 0 22px rgba(164, 140, 242, 0.35)",
        "glow-magenta": "0 0 22px rgba(244, 95, 176, 0.35)",
        "glow-amber": "0 0 22px rgba(245, 193, 108, 0.35)",
        "glow-red": "0 0 22px rgba(242, 85, 92, 0.35)",
        "glow-green": "0 0 22px rgba(67, 224, 160, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
