import type { Config } from "@docusaurus/types";
import type { Preset } from "@docusaurus/preset-classic";

const config: Config = {
  title: "Truth's Forge AI Docs",
  tagline: "Arquitetura, decisões e operação local-first",

  url: "http://127.0.0.1:3000",
  baseUrl: "/",

  organizationName: "truths-forge",
  projectName: "truths-forge-ai",

  onBrokenLinks: "warn",

  i18n: {
    defaultLocale: "pt-BR",
    locales: ["pt-BR"]
  },

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: "warn"
    }
  },

  presets: [
    [
      "classic",
      {
        docs: {
          path: "../../docs",
          routeBasePath: "docs",
          sidebarPath: "./sidebars.ts"
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css"
        }
      } satisfies Preset.Options
    ]
  ],

  themes: ["@docusaurus/theme-mermaid"],

  themeConfig: {
    navbar: {
      title: "Truth's Forge AI",
      items: [
        {
          type: "docSidebar",
          sidebarId: "docsSidebar",
          position: "left",
          label: "Docs"
        },
        {
          href: "http://127.0.0.1:5173",
          label: "Aplicação",
          position: "right"
        },
        {
          href: "http://127.0.0.1:8000/docs",
          label: "OpenAPI",
          position: "right"
        }
      ]
    },
    footer: {
      style: "dark",
      copyright: `Truth's Forge AI - documentação local`
    },
    prism: {
      theme: require("prism-react-renderer").themes.github,
      darkTheme: require("prism-react-renderer").themes.dracula
    }
  } satisfies Preset.ThemeConfig
};

export default config;
