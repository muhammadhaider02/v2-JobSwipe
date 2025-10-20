/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/upload', destination: 'http://localhost:5000/upload' },
      { source: '/api/health', destination: 'http://localhost:5000/health' },
    ];
  },
};

module.exports = nextConfig;


