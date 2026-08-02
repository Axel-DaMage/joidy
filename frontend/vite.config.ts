import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';

// The browser connects to the host-mapped frontend port, which may differ from
// the container's internal port (3000) when FRONTEND_PORT is overridden.
const FRONTEND_PORT =
  (typeof process !== 'undefined' && Number(process.env.FRONTEND_PORT)) || 3000;

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: true,
    hmr: {
      // When running inside Docker, the browser connects to the host-mapped
      // port. Without this, Vite tries to connect the WS to the container's
      // internal address and the browser gets a connection refused error.
      clientPort: FRONTEND_PORT,
      host: 'localhost'
    }
  },
  ssr: {
    noExternal: ['phosphor-svelte', 'svelte-hero-icons', 'svelte-bootstrap-icons', 'svelte-radix']
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Visualization: d3 + force-graph (used by SkillTree, KnowledgeGraph)
          d3: ['d3', 'force-graph'],
          // Markdown rendering: marked + dompurify + highlight.js (used by
          // NoteEditor, GoalEditor, ChatInterface, WysiwygEditor)
          markdown: ['marked', 'dompurify', 'highlight.js'],
          // Rich text editor: TipTap + extensions (used by WysiwygEditor)
          tiptap: [
            '@tiptap/core',
            '@tiptap/starter-kit',
            '@tiptap/pm',
            '@tiptap/extension-code-block-lowlight',
            '@tiptap/extension-image',
            '@tiptap/extension-link',
            '@tiptap/extension-placeholder',
            '@tiptap/extension-strike',
            '@tiptap/extension-task-item',
            '@tiptap/extension-task-list',
            '@tiptap/extension-underline'
          ]
        }
      }
    }
  }
});
