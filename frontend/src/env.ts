// Explicit env vars for Kit 3's typed environment system — imported from
// `$app/env/public` (the legacy `$env/dynamic/public` is deprecated and no
// longer picks up PUBLIC_* vars automatically).
import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
  // docker-compose.yml injects the resolved API port as PUBLIC_API_PORT
  // (`${API_PORT:-8000}`, possibly bumped by `joidy up` port-fallback).
  // public + non-static → read at request time and rendered into the page
  // payload, so the SPA learns the real port without an image rebuild (#1487).
  PUBLIC_API_PORT: {
    public: true,
    // Optional — unset/empty yields undefined and the browser falls back to
    // VITE_API_URL, then <page-host>:8000 (see lib/utils/apiBase.ts).
    schema: (value) => value || undefined,
    description:
      'Host port the API is published on (compose API_PORT, after joidy up port-fallback).',
  },
});
