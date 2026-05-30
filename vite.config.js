import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig({

    plugins: [
        tailwindcss(),
    ],
    
    base: '/static/',
    
    build: {

        outDir: 'dist',
        rollupOptions: {
            input: 'src/js/main.js'
        }

    },

    server: {

        host: '0.0.0.0',
        port: 5173,
        hmr: {
            host: 'localhost'
        }

    }
})