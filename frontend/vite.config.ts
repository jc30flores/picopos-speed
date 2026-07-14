import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(() => ({
  server: {
    host: true,
    allowedHosts: ["la-rosee.cuskatech.com"],
    port: 8386,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8306",
        changeOrigin: true,
        secure: false,
        timeout: 120000,
        proxyTimeout: 120000,
      },
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
