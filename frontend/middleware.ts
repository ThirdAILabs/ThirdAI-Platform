export { default } from 'next-auth/middleware';

// Don't invoke Middleware since we handle in backend
export const config = {
  matcher: [],
};
