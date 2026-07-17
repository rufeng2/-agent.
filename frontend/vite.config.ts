import { defineConfig, loadEnv } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "")
  const apiTarget = env.VITE_API_TARGET || "http://127.0.0.1:8001"

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        "@": "/src",
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            const has = (value: string) => id.indexOf(value) >= 0
            if (has("node_modules/vue") || has("node_modules/vue-router") || has("node_modules/pinia") || has("node_modules/axios")) {
              return "vue-vendor"
            }
            if (has("node_modules/@element-plus/icons-vue")) {
              return "element-plus-icons"
            }
          },
        },
      },
    },
  }
})
