import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { execSync } from 'node:child_process';
import pkg from './package.json' with { type: 'json' };
import { kitOptions } from './kit.options';

// The browser connects to the host-mapped frontend port, which may differ from
// the container's internal port (3000) when FRONTEND_PORT is overridden.
const FRONTEND_PORT = (typeof process !== 'undefined' && Number(process.env.FRONTEND_PORT)) || 3000;

// Commit the bundle was built from — surfaced in the status bar under dev mode
// so it is obvious which build a tab is actually running (stale service-worker
// precaches otherwise look identical). Docker images get it via --build-arg
// GIT_SHA (.git is dockerignored); host builds fall back to `git rev-parse`.
const GIT_SHA = (() => {
  if (process.env.VITE_GIT_SHA) return process.env.VITE_GIT_SHA;
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .trim();
  } catch {
    return '';
  }
})();

export default defineConfig({
  plugins: [sveltekit(kitOptions)],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __GIT_SHA__: JSON.stringify(GIT_SHA),
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
    // phosphor-svelte ships untranspiled Svelte — the other three entries were
    // for packages that are not installed anymore (#1311).
    noExternal: ['phosphor-svelte'],
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
