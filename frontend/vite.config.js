import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "../static_dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/analyze": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/tools": "http://127.0.0.1:8000",
      "/trade": "http://127.0.0.1:8000",
      "/backtest": "http://127.0.0.1:8000",
      "/risk": "http://127.0.0.1:8000",
      "/ai": "http://127.0.0.1:8000",
    },
  },
});
