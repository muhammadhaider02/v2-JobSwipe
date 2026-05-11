/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/upload', destination: `${BACKEND_URL}/upload` },
      { source: '/api/health', destination: `${BACKEND_URL}/health` },
    ];
  },
};

module.exports = nextConfig;


