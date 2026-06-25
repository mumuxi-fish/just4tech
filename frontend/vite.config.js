import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import prerender from 'vite-plugin-prerender'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    prerender({
      staticDir: 'dist',
      routes: ['/', '/blog', '/aitools', '/about', '/contact'],
    }),
  ],
  base: '/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('highlight.js')) return 'highlight'
          if (id.includes('node_modules/vue')) return 'vendor'
        }
      }
    }
  }
})
