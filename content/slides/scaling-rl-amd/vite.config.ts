import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Base "./" so the built bundle works when served from any sub-path
// (HF Spaces static hosting serves from the Space root).
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { host: true, port: 5173 },
});
