import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// No build-time configuration of any kind (VITE_* or otherwise) — the SPA
// calls the API through relative /api/v1 paths only, so a build produced on
// a developer machine behaves identically in production (architecture.md §9).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
