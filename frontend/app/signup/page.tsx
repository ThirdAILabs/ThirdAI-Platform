import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { signIn } from '@/lib/auth';
import SignupForm from './signup-form';
import Link from 'next/link'

export default function SignupPage() {

  return (
    <div className="min-h-screen flex justify-center items-start md:items-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Sign up</CardTitle>
          <CardDescription>
            Please fill in the details to create an account.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <SignupForm/>

          <Link href="/login-email">
            <button type="button">
              Log In
            </button>
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
