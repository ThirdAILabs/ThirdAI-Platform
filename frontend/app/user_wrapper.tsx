'use client';

import { getAccessToken, User, accessTokenUser } from '@/lib/backend';
import { access } from 'fs';
import { useRouter } from 'next/navigation';
import { useEffect, useState, createContext, SetStateAction, Dispatch } from 'react';

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

  const logout = () => {
    setAccessToken(null);
    localStorage.removeItem('accessToken');
    setUser(null);
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
        router.push('/login-email');
      }
    });
  }, [accessToken]);

  return (
    <UserContext.Provider value={{ user, accessToken, setAccessToken, logout }}>
      {children}
    </UserContext.Provider>
  );
}
