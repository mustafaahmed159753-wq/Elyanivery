import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  async rewrites() {
    return [
      { source: "/customer", destination: "/customer/index.html" },
      { source: "/courier", destination: "/courier/index.html" },
      { source: "/partner", destination: "/partner/index.html" },
      { source: "/admin", destination: "/admin/index.html" },
      { source: "/support", destination: "/support/index.html" },
    ];
  },
};

export default nextConfig;
