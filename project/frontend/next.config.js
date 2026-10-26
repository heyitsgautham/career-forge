/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async redirects() {
    return [
      // The profile editor lives in the dashboard's profile tab.
      { source: '/dashboard/profile', destination: '/dashboard?tab=profile', permanent: false },
      // Resumes are generated from the dialog on the resumes tab.
      { source: '/dashboard/resumes/new', destination: '/dashboard?tab=resumes', permanent: false },
    ];
  },
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
