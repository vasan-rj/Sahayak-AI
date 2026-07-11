/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: the browser talks to Vite, Vite forwards /ws, /health, /verify to
// the FastAPI proxy on :8000. In production the proxy serves the built dist.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/health": "http://localhost:8000",
      "/verify": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
