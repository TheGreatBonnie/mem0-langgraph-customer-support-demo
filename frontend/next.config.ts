import type { NextConfig } from "next";

const supportApiBaseUrl = process.env.SUPPORT_API_BASE_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/support-api/:path*",
        destination: `${supportApiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
