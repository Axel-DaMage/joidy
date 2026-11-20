import { json } from '@sveltejs/kit';

export function GET() {
  return json(
    {
      id: '/',
      name: 'Joidy',
      short_name: 'Joidy',
      description: 'Personal Knowledge Management with Gamification',
      lang: 'es',
      dir: 'ltr',
      start_url: '/',
      scope: '/',
      display: 'standalone',
      // Brand accent instead of pure black so the launch splash does not
      // force a dark screen on light-theme users (#1310).
      background_color: '#c8a96e',
      theme_color: '#c8a96e',
      categories: ['productivity', 'notes'],
      icons: [
        {
          src: '/icons/icon-192.png',
          sizes: '192x192',
          type: 'image/png',
          purpose: 'any',
        },
        {
          src: '/icons/icon-512.png',
          sizes: '512x512',
          type: 'image/png',
          purpose: 'any',
        },
        {
          src: '/icons/icon-maskable-512.png',
          sizes: '512x512',
          type: 'image/png',
          purpose: 'maskable',
        },
      ],
      shortcuts: [
        {
          name: 'Notes',
          url: '/notes',
          icons: [{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' }],
        },
        {
          name: 'Goals',
          url: '/goals',
          icons: [{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' }],
        },
      ],
    },
    {
      headers: {
        'Cache-Control': 'max-age=86400',
      },
    }
  );
}
