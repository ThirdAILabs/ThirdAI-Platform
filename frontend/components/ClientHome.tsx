'use client';

import { useEffect, useContext, useState } from 'react';
import { useSession, signIn } from 'next-auth/react';
import { UserContext } from '../app/user_wrapper';
import { SyncKeycloakUser } from '@/lib/backend';
import { useRouter } from 'next/navigation';

export default function ClientHome() {
  const { data: session, status } = useSession();
  const { setAccessToken } = useContext(UserContext);
  const [backendLoginAttempted, setBackendLoginAttempted] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (status === 'loading') {
      return;
    }

    if (status === 'unauthenticated') {
      signIn('keycloak', { callbackUrl: '/' });
    }

    if (status === 'authenticated' && !backendLoginAttempted) {
      setBackendLoginAttempted(true);
      if (session?.accessToken) {
        SyncKeycloakUser(session.accessToken, setAccessToken)
          .then(() => {
            router.replace('/');
          })
          .catch((error) => {
            console.error('Failed to fetch user data:', error);
          });
      } else {
        console.error('No access token found in session');
      }
    }
  }, [status, session, backendLoginAttempted, router]);

  return null;
}
