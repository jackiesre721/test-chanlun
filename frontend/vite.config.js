import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
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
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
});
