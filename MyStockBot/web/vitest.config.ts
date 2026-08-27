import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 테스트 설정을 vite.config.ts 와 **분리한 이유**:
// vitest 는 자체 vite(rollup 기반)를 번들해 오는데 이 프로젝트는 vite 8(rolldown 기반)이라,
// 한 파일에서 두 타입이 만나면 플러그인 시그니처가 충돌해 `tsc -b` 가 실패한다.
// 러너 설정만 여기 두고 프로덕션 빌드 설정(PWA·프록시)은 vite.config.ts 에 남긴다.
// 이 파일은 tsconfig.node.json 의 include 밖이라 빌드 타입체크 대상이 아니다.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    exclude: ["node_modules/**", "dist/**"],
  },
});
