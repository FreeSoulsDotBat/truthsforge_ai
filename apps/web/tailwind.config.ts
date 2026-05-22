import type { Config } from "tailwindcss";

/*
 * Identidade visual v4 "Hearth": as cores forge-* apontam para CSS vars
 * declaradas em src/styles.css (themeVars(HEARTH)). Os nomes Tailwind são
 * preservados — forge-amber/forge-blue continuam válidos e passam a render
 * ember/azure automaticamente, re-tonando os arquivos existentes sem editá-los.
 */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forge: {
          ink: "var(--bg)",
          panel: "var(--bg-card)",
          elev: "var(--bg-elev)",
          chip: "var(--bg-chip)",
          hover: "var(--bg-hover)",
          "ink-deep": "var(--bg-ink)",
          line: "var(--line)",
          "line-soft": "var(--line-soft)",
          text: "var(--text)",
          "text-soft": "var(--text-soft)",
          muted: "var(--muted)",
          faint: "var(--faint)",
          amber: "var(--ember)",
          "amber-soft": "var(--ember-soft)",
          "amber-ink": "var(--ember-ink)",
          amethyst: "var(--amethyst)",
          "amethyst-soft": "var(--amethyst-soft)",
          blue: "var(--azure)",
          "blue-soft": "var(--azure-soft)",
          green: "var(--ok)",
          red: "var(--err)"
        }
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-text)"],
        serif: ["var(--font-serif)"],
        mono: ["var(--font-mono)"]
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        lg: "var(--radius-lg)"
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
        glow: "var(--shadow-glow)"
      }
    }
  },
  plugins: []
} satisfies Config;
