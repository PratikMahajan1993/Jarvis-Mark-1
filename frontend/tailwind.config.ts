import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#061018",
        panel: "#0b1c28",
        cyan: "#3ee0d4",
        amber: "#f5c16c",
      },
      fontFamily: {
        display: ["Rajdhani", "Segoe UI", "sans-serif"],
        body: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        hud: "0 0 40px rgba(62, 224, 212, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
