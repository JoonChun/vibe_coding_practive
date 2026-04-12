import { defineConfig } from 'vite';
import { resolve } from 'path';

// Content script는 Chrome이 ES 모듈을 지원하지 않으므로 IIFE 형식으로 별도 빌드
export default defineConfig({
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: false, // 메인 빌드 결과물을 지우지 않음
    rollupOptions: {
      input: {
        content: resolve(__dirname, 'src/content/index.ts'),
      },
      output: {
        format: 'iife',
        entryFileNames: '[name].js',
        inlineDynamicImports: true,
      },
    },
  },
});
