import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: 'all',
    hmr: {
      // When running inside Docker, the browser connects to the host-mapped
      // port. Without this, Vite tries to connect the WS to the container's
      // internal address and the browser gets a connection refused error.
      clientPort: 3000,
      host: 'localhost'
    }
  },
  ssr: {
    noExternal: ['phosphor-svelte', 'svelte-hero-icons', 'svelte-bootstrap-icons', 'svelte-radix']
  }
});
