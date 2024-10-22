'use client';
import { signIn } from 'next-auth/react';
import { useState } from 'react';

export default function Login() {
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    try {
      await signIn('keycloak');
    } catch (error) {
      console.error('Login process failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleLogin}
      className="bg-sky-500 hover:bg-sky-700 px-5 py-2 text-sm leading-5 rounded-full font-semibold text-white"
      disabled={loading}
    >
      {loading ? 'Signing in...' : 'Signin with Keycloak'}
    </button>
  );
}
