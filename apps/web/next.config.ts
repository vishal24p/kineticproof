import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Match the API file limit plus its multipart allowance.
    proxyClientMaxBodySize: 100_065_536,
    // Allow a valid 30-second clip to finish tracking and overlay encoding.
    proxyTimeout: 300_000,
  },
  async rewrites() {
    const apiOrigin = (
      process.env.KINETICPROOF_API_ORIGIN ?? "http://127.0.0.1:8000"
    ).replace(/\/$/, "");

    return [
      { source: "/api/health", destination: `${apiOrigin}/health` },
      { source: "/api/:path*", destination: `${apiOrigin}/api/:path*` },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
