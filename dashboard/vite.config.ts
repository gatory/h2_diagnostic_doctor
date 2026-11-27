import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// tailwindcss(): reads the classes used in src/ and generates their CSS (styles: src/index.css).
export default defineConfig({
  plugins: [react(), tailwindcss()],
})
