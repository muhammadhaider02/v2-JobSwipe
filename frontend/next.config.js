/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/api/jobs/:path*', destination: `${BACKEND_URL}/api/jobs/:path*` },
      { source: '/api/:path*', destination: `${BACKEND_URL}/:path*` },
    ];
  },
};

module.exports = nextConfig;


