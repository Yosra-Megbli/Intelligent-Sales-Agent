import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(async () => {
  const { default: tailwindcss } = await import("@tailwindcss/vite");
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": {
          target: "https://intelligent-sales-agent.onrender.com",
          changeOrigin: true,
          secure: true,
        },
      },
    },
  };
});
