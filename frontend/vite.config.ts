/// <reference types="vitest/config" />
import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Three pages: index.html (marketing landing, the entry at "/"), app.html (the
// applicant voice app), admin.html (admin dashboard). Dev proxy forwards the API
// + WS to the FastAPI proxy on :8000. In production the proxy serves the built
// dist; StaticFiles(html=True) serves index.html (= landing) at "/".
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        landing: resolve(__dirname, "index.html"),
        app: resolve(__dirname, "app.html"),
        admin: resolve(__dirname, "admin.html"),
      },
    },
  },
  server: {
    // Dev (:5173) serves all three HTML pages itself (with HMR); only the API +
    // WS are proxied to the FastAPI backend on :8000. NOTE the trailing slash on
    // "/admin/": it proxies the admin API but NOT "/admin.html" (that page must
    // stay local to vite). "/template" also covers "/templates".
    proxy: {
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/health": "http://localhost:8000",
      "/template": "http://localhost:8000",
      "/admin/": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
