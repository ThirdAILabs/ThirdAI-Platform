import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import ClientHome from '../../components/ClientHome';

export default async function Home() {
  const session = await getServerSession(authOptions);

  const accessToken = session?.accessToken;

  return <ClientHome session={session} accessToken={accessToken} />;
}
