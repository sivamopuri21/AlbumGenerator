/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:8001/api/:path*" },
    ];
  },
  experimental: {
    proxyTimeout: 600000,
  },
};

module.exports = nextConfig;
