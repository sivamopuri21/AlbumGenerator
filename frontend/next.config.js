/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: { unoptimized: true },
  // For web dev mode, use this instead:
  // async rewrites() {
  //   return [{ source: "/api/:path*", destination: "http://localhost:8001/api/:path*" }];
  // },
};

module.exports = nextConfig;
