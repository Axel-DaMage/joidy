import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';
import pkg from './package.json';

// The browser connects to the host-mapped frontend port, which may differ from
// the container's internal port (3000) when FRONTEND_PORT is overridden.
const FRONTEND_PORT = (typeof process !== 'undefined' && Number(process.env.FRONTEND_PORT)) || 3000;

export default defineConfig({
  plugins: [sveltekit()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  esbuild: {
    target: 'esnext',
  },
  optimizeDeps: {
    esbuildOptions: {
      target: 'esnext',
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: true,
    hmr: {
      // When running inside Docker, the browser connects to the host-mapped
      // port. Without this, Vite tries to connect the WS to the container's
      // internal address and the browser gets a connection refused error.
      clientPort: FRONTEND_PORT,
      host: 'localhost',
    },
  },
  ssr: {
    noExternal: ['phosphor-svelte', 'svelte-hero-icons', 'svelte-bootstrap-icons', 'svelte-radix'],
  },
  build: {
    target: 'esnext',
    rollupOptions: {
      output: {
        // Function form: only group modules resolved from `node_modules`.
        // SvelteKit externalizes some deps (e.g. d3, force-graph) for the SSR
        // build pass, where their ids are bare specifiers without a
        // `node_modules` segment. The object form tried to chunk those bare
        // specifiers and aborted the build with
        // "d3 cannot be included in manualChunks because it is resolved as an
        // external module". Skipping non-node_modules ids avoids that.
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          // Visualization: d3 + force-graph (used by SkillTree, KnowledgeGraph)
          if (id.includes('/d3/') || id.includes('/force-graph/')) return 'd3';
          // Markdown rendering: marked + dompurify + highlight.js (used by
          // NoteEditor, GoalEditor, ChatInterface, WysiwygEditor)
          if (
            id.includes('/marked/') ||
            id.includes('/dompurify/') ||
            id.includes('/highlight.js/')
          ) {
            return 'markdown';
          }
          // Rich text editor: TipTap + extensions (used by WysiwygEditor)
          if (id.includes('/@tiptap/')) return 'tiptap';
        },
      },
    },
  },
});
