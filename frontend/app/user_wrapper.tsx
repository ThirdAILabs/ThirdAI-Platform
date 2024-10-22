'use client';

import { getAccessToken, User, accessTokenUser } from '@/lib/backend';
import { useRouter } from 'next/navigation';
import { useEffect, useState, createContext, SetStateAction, Dispatch } from 'react';
import federatedLogout from '@/utils/federatedLogout';

interface UserContext {
  user: User | null;
  accessToken?: string | null;
  setAccessToken: Dispatch<SetStateAction<string | null | undefined>>;
  logout: () => void;
}

// Dummy default values. They will be correctly initialized by the time the context is
// used by the provider's children.
export const UserContext = createContext<UserContext>({
  user: null,
  accessToken: null,
  setAccessToken: (user) => {},
  logout: () => {},
});

export default function UserWrapper({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [accessToken, setAccessToken] = useState<string | null | undefined>();
  const [user, setUser] = useState<User | null>(null);

  const logout = async () => {
    setAccessToken(null);
    localStorage.removeItem('accessToken');
    setUser(null);
    await federatedLogout();

    if (
      process.env.NEXT_PUBLIC_IDENTITY_PROVIDER &&
      process.env.NEXT_PUBLIC_IDENTITY_PROVIDER.toLowerCase().includes('keycloak')
    ) {
      router.push('/login-keycloak');
    } else {
      router.push('/login-email');
    }
  };

  useEffect(() => {
    setAccessToken(getAccessToken(/* throwIfNotFound= */ false));
  }, []);

  useEffect(() => {
    if (accessToken === undefined) {
      return;
    }
    accessTokenUser(accessToken).then((user) => {
      setUser(user);
      if (!user) {
        if (
          process.env.NEXT_PUBLIC_IDENTITY_PROVIDER &&
          process.env.NEXT_PUBLIC_IDENTITY_PROVIDER.toLowerCase().includes('keycloak')
        ) {
          router.push('/login-keycloak');
        } else {
          router.push('/login-email');
        }
      }
    });
  }, [accessToken]);

  return (
    <UserContext.Provider value={{ user, accessToken, setAccessToken, logout }}>
      {children}
    </UserContext.Provider>
  );
}
