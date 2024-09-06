'use client'

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { EyeIcon, EyeOffIcon } from '@heroicons/react/solid';
import { userRegister } from '@/lib/backend';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function SignupForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [showPassword, setShowPassword] = useState(false);
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
      console.log(err);
    }
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
        <div className="mb-4">
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
            <input
                type="email"
                id="email"
                className="mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md focus:outline-none focus:border-transparent"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
            />
        </div>
        <div className="mb-4 relative">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
            <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                className="mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md pr-10 focus:outline-none focus:border-transparent"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            />
            <button
              type="button"
              onClick={togglePasswordVisibility}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-gray-700"
            >
              {showPassword ? (
                <EyeOffIcon className="h-5 w-5" aria-hidden="true" />
              ) : (
                <EyeIcon className="h-5 w-5" aria-hidden="true" />
              )}
            </button>
        </div>
        <div className="mb-4">
            <label htmlFor="username" className="block text-sm font-medium text-gray-700">Username</label>
            <input
                type="text"
                id="username"
                className="mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md focus:outline-none focus:border-transparent"
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
