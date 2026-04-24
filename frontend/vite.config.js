import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        // In dev mode, proxy /api requests to the FastAPI backend
        proxy: {
            "/api": "http://localhost:8000",
        },
    },
    // Build output goes to frontend/dist — FastAPI serves it as static files
    build: {
        outDir: "dist",
    },
});
