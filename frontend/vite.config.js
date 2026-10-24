import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During dev (npm run dev) the frontend runs on :5173 and proxies /api to the
// backend on :8000, so there are no CORS surprises. In production the build is
// served by FastAPI from the same origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
