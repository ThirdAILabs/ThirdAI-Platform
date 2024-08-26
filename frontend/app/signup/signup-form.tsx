'use client'

import { useState } from 'react';
import { Button } from '@/components/ui/button';

import { signIn } from '@/lib/auth';
import { userRegister } from "@/lib/backend";
import { useRouter } from 'next/navigation';
import Link from 'next/link'

export default function SignupForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');

  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const data = await userRegister(email, password, username);
      console.log('User registered successfully:', data);
      router.push('/login-email');
      // Redirect or show success message
    } catch (err) {
      console.log(err)
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
        <div className="mb-4">
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
            <input
                type="email"
                id="email"
                className="mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
            />
        </div>
        <div className="mb-4">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
            <input
                type="password"
                id="password"
                className="mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            />
        </div>
        <div className="mb-4">
            <label htmlFor="username" className="block text-sm font-medium text-gray-700">Username</label>
            <input
                type="text"
                id="username"
                className="mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
            />
        </div>
        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

        <div className="flex items-center">
          <Button type="submit" className="flex-grow mr-2">
            Sign Up
          </Button>
          <Link href="/login-email" className="w-auto">
            <Button type="button" className="w-full">
              Log In
            </Button>
          </Link>
        </div>
    </form>
  );
}
