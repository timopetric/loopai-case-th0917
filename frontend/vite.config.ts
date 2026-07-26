import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// No build-time configuration of any kind (VITE_* or otherwise) — the SPA
// calls the API through relative /api/v1 paths only, so a build produced on
// a developer machine behaves identically in production (architecture.md §9).
// Tailwind is CSS tooling, not an environment value baked into the bundle
// (issue 01, frontend-rework), so it's exempt from that rule.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
