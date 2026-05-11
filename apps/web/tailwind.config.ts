import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forge: {
          ink: "#0c0d0f",
          panel: "#171716",
          line: "#313334",
          text: "#e7edf5",
          muted: "#a2a09a",
          blue: "#4aa3ff",
          green: "#62d98b",
          red: "#ff6b6b",
          amber: "#f0b84d"
        }
      },
      boxShadow: {
        soft: "0 18px 40px rgba(0, 0, 0, 0.28)"
      }
    }
  },
  plugins: []
} satisfies Config;
