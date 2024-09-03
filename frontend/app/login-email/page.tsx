'use client'

import { useContext, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { userEmailLogin } from '@/lib/backend';
import Link from 'next/link'
import { UserContext } from '../user_wrapper';

export default function LoginPage() {
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const { setAccessToken } = useContext(UserContext);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); // Clear any previous errors
    try {
      const data = await userEmailLogin(email, password, setAccessToken);
      console.log('User logged in successfully:', data);
      // Redirect to the home page
      window.location.href = '/';
    } catch (err) {
      console.log(err);
      setError('Login failed. Please check your email and password.');
    }
  };

  return (
    <div className="min-h-screen flex justify-center items-start md:items-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Login</CardTitle>
          <CardDescription>
            Please enter your email and password to login.
          </CardDescription>
        </CardHeader>
        <CardFooter>
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
            {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
            
            <div className="flex items-center justify-between mb-4">
              <Button type="submit" className="w-full">Login</Button>
              <Link href="/signup" className="ml-4">
                <Button type="button" className="w-full">Sign up</Button>
              </Link>
            </div>
          </form>
        </CardFooter>
      </Card>
    </div>
  );
}
