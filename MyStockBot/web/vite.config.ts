import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // 개인용 앱: dev 서버에서는 SW 미활성 (기본값 유지)
      manifest: {
        name: "MyStockBot",
        short_name: "MyStockBot",
        description: "내 관심종목 매매신호 대시보드",
        lang: "ko",
        theme_color: "#091426",
        background_color: "#fbf8fa",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/icons/icon-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // SPA fallback이 /api 요청을 가로채지 않도록 제외
        navigateFallbackDenylist: [/^\/api\//],
        // 시세 신선도가 생명 — API 응답은 절대 캐시하지 않음 (runtimeCaching 미설정)
        // 빌드 산출물(js/css/html/png)만 프리캐시
      },
    }),
  ],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "http://localhost:8000", ws: true },
    },
  },
});
