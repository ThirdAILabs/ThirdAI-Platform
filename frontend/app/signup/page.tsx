import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import SignupForm from './signup-form';

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
        </CardFooter>
      </Card>
    </div>
  );
}
