import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "ai.truthsforge.app",
  appName: "Truth's Forge AI",
  webDir: "../web/dist",
  server: {
    androidScheme: "https"
  }
};

export default config;
