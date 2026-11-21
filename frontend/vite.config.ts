import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API + OAuth routes to the FastAPI backend during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
