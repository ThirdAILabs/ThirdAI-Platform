/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'avatars.githubusercontent.com'
      },
      {
        protocol: 'https',
        hostname: '*.public.blob.vercel-storage.com'
      }
    ]
  },
  env: {
    DEPLOYMENT_BASE_URL: process.env.DEPLOYMENT_BASE_URL,
    THIRDAI_PLATFORM_BASE_URL: process.env.THIRDAI_PLATFORM_BASE_URL,
  }
};

module.exports = nextConfig;
