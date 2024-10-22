// components/ClientHome.tsx
'use client';

import { useContext } from 'react';
import { useEffect } from 'react';
import Login from '@/components/Login';
import { userEmailLoginWithAccessToken } from '@/lib/backend';
import { UserContext } from '../app/user_wrapper';
import { Session } from 'next-auth';

interface ClientHomeProps {
  session: Session | null; // Session type from next-auth
  accessToken: string | null | undefined; // accessToken is a string
}

export default function ClientHome({ session, accessToken }: ClientHomeProps) {
  const { setAccessToken } = useContext(UserContext);

  useEffect(() => {
    if (accessToken) {
      userEmailLoginWithAccessToken(accessToken, setAccessToken)
        .then(() => {
          if (session) {
            window.location.href = '/';
          }
        })
        .catch((error) => {
          console.error('Failed to log in with email using the access token:', error);
        });
    }
  }, [accessToken]);

  return (
    <div className="flex flex-col space-y-3 justify-center items-center h-screen">
      {!session && <Login />}
    </div>
  );
}
