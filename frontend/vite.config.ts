import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';
import pkg from './package.json' with { type: 'json' };
import { kitOptions } from './kit.options';

// The browser connects to the host-mapped frontend port, which may differ from
// the container's internal port (3000) when FRONTEND_PORT is overridden.
const FRONTEND_PORT = (typeof process !== 'undefined' && Number(process.env.FRONTEND_PORT)) || 3000;

export default defineConfig({
  plugins: [sveltekit(kitOptions)],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  esbuild: {
    target: 'esnext',
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: true,
    hmr: {
      // When running inside Docker, the browser connects to the host-mapped
      // port. Without this, Vite tries to connect the WS to the container's
      // internal address and the browser gets a connection refused error.
      // Use 127.0.0.1 (IPv4) instead of 'localhost' to avoid Docker's broken
      // IPv6 forwarding on some hosts (e.g. Arch Linux) where ::1 hangs.
      clientPort: FRONTEND_PORT,
      host: process.env.JOIDY_HMR_HOST || '127.0.0.1',
    },
  },
  ssr: {
    noExternal: ['phosphor-svelte', 'svelte-hero-icons', 'svelte-bootstrap-icons', 'svelte-radix'],
  },
  build: {
    target: 'esnext',
    rollupOptions: {
      output: {
        // Rolldown's advancedChunks replaces manualChunks (Vite 8). The `test`
        // regexes only match ids containing `node_modules`, so SSR-externalized
        // deps resolved as bare specifiers (e.g. `d3`) are never chunked — the
        // reason the old function form existed.
        advancedChunks: {
          groups: [
            // Visualization: d3 + force-graph (used by SkillTree, KnowledgeGraph)
            { name: 'd3', test: /node_modules\/(d3|force-graph)\// },
            // Markdown rendering: marked + dompurify + highlight.js (used by
            // NoteEditor, GoalEditor, ChatInterface, WysiwygEditor)
            { name: 'markdown', test: /node_modules\/(marked|dompurify|highlight\.js)\// },
            // Rich text editor: TipTap + extensions (used by WysiwygEditor)
            { name: 'tiptap', test: /node_modules\/@tiptap\// },
          ],
        },
      },
    },
  },
});
