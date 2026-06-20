import { json } from '@sveltejs/kit';

export function GET() {
  return json({
    name: "Joidy",
    short_name: "Joidy",
    description: "Personal Knowledge Management with Gamification",
    start_url: "/",
    display: "standalone",
    background_color: "#000000",
    theme_color: "#c8a96e",
    icons: [
      {
        src: "/favicon.png",
        sizes: "192x192",
        type: "image/png"
      },
      {
        src: "/favicon.png",
        sizes: "512x512",
        type: "image/png"
      }
    ]
  }, {
    headers: {
      'Cache-Control': 'max-age=86400',
    }
  });
}