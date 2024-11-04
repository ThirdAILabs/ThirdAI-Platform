'use client';
import { signIn, useSession } from 'next-auth/react';
import { useEffect, useState } from 'react';

export default function SessionGuard() {
  const { data: session } = useSession();
  const [tokenCheckInterval, setTokenCheckInterval] = useState<NodeJS.Timeout | null>(null);

  const checkAndRefreshToken = async () => {
    const accessToken = session?.accessToken;
    const expiresAt = session?.expiresAt || 0;

    if (accessToken && Date.now() >= expiresAt * 1000 - 60 * 1000) {
      await signIn('keycloak'); // Trigger refresh using NextAuth's built-in refresh mechanism
    }
  };

  useEffect(() => {
    if (session?.error === 'RefreshAccessTokenError') {
      signIn('keycloak');
    }

    if (session?.accessToken) {
      localStorage.setItem('accessToken', session.accessToken);
      if (!tokenCheckInterval) {
        const interval = setInterval(checkAndRefreshToken, 60 * 1000);
        setTokenCheckInterval(interval);
      }
    }

    return () => {
      if (tokenCheckInterval) {
        clearInterval(tokenCheckInterval);
        setTokenCheckInterval(null);
      }
    };
  }, [session, tokenCheckInterval]);

  return null;
}
