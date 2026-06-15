import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig(({ command, mode }) => {
    const isProduction = mode === 'production';

    return {
        plugins: [], 
        base: isProduction ? '/static/' : '/',
        build: {
            manifest: true,
            outDir: path.resolve(__dirname, 'static/dist'),
            emptyOutDir: true,
            rollupOptions: {
                input: path.resolve(__dirname, 'static/src/js/main.js')
            }
        },
        server: {
            host: '0.0.0.0',
            port: 5173,
            strictPort: true,
            watch: { usePolling: true },
            hmr: { clientPort: 5173 }
        }
    };
});