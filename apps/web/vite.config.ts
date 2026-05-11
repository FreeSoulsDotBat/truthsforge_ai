import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const usePolling = process.env.VITE_USE_POLLING === "true";
const pollingInterval = Number(process.env.VITE_POLLING_INTERVAL ?? "150");

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    watch: usePolling
      ? {
          usePolling: true,
          interval: Number.isFinite(pollingInterval) ? pollingInterval : 150
        }
      : undefined
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts"
  }
});
