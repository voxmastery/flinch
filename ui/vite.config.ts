import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const DAEMON = "http://127.0.0.1:7331";

export default defineConfig({
  base: "/",
  plugins: [react()],
  build: {
    outDir: "../flinch/ui/dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/events": { target: DAEMON, changeOrigin: true },
      "/api": { target: DAEMON, changeOrigin: true },
    },
  },
});
