/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone output for Docker/Railway — Netlify handles its own bundling
  output: process.env.NETLIFY ? undefined : "standalone",
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      // NOTE: do NOT rewrite /api/v1/* here. Those requests must go through the
      // route handler at app/api/v1/[...path]/route.ts, which injects the
      // session's bearer token. A rewrite runs before route handlers and would
      // forward to the backend with no Authorization header → 401.
      {
        source: "/reports/:path*",
        destination: `${api}/reports/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
