import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the FastAPI backend directly over HTTP (see
// src/lib/config.ts, VITE_API_BASE) rather than through a Vite dev proxy —
// the backend's CORS middleware already allows http://localhost:5173 (see
// backend/.env.example's ALLOWED_ORIGIN default), so there's nothing a
// proxy would add for local dev that direct calls don't already have.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { outDir: "dist", sourcemap: true },
});
