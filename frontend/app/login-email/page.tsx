'use client';

import { useContext, useState } from 'react';
import { Button, TextField } from '@mui/material';

import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';

import { userEmailLogin } from '@/lib/backend';
import Link from 'next/link';
import { UserContext } from '../user_wrapper';
import { EyeIcon, EyeOffIcon } from '@heroicons/react/solid';
import axios from 'axios';

export default function LoginPage() {
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const { setAccessToken } = useContext(UserContext);

  const [showPassword, setShowPassword] = useState(false);

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); // Clear any previous errors
    try {
      const data = await userEmailLogin(email, password, setAccessToken);
      console.log('User logged in successfully:', data);
      // Redirect to the home page
      window.location.href = '/';
    } catch (err: any) {
      console.log(err);
      if (axios.isAxiosError(err) && err.response) {
        // If it's an Axios error and we have a response
        setError(
          err.response.data.message || 'Login failed. Please check your email and password.'
        );
      } else {
        // Fallback to generic error if it's not an Axios error or no response is available
        setError('Login failed. Please check your email and password.');
      }
    }
  };

  return (
    <div className="min-h-screen flex justify-center items-start md:items-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Login</CardTitle>
          <CardDescription>Please enter your email and password to login.</CardDescription>
        </CardHeader>
        <CardFooter>
          <form onSubmit={handleSubmit} className="w-full">
            <div className="mb-4">
              <TextField
                type="email"
                id="email"
                placeholder="Email"
                className="w-full"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="mb-4 relative">
              <TextField
                type={showPassword ? 'text' : 'password'}
                id="password"
                placeholder="Password"
                className="w-full"
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
            {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

            <div className="flex items-center justify-between mb-4">
              <Button type="submit" variant="contained" className="flex-grow mr-2">
                Login
              </Button>
              <Link href="/signup" className="ml-4">
                <Button type="button" variant="contained" className="w-full">
                  Sign up
                </Button>
              </Link>
            </div>
          </form>
        </CardFooter>
      </Card>
    </div>
  );
}
