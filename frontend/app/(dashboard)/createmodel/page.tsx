import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import ChooseProblem from './choose-model';

export default async function NewModelPage({
  searchParams,
}: {
  searchParams: { q: string; offset: string };
}) {
  return (
    <div
      style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'center',
        background: 'transparent',
      }}
    >
      <Card style={{ width: '100%', maxWidth: '700px' }}>
        <CardHeader>
          <CardTitle>Create App</CardTitle>
          <CardDescription>Create a new application with a few simple steps.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChooseProblem />
        </CardContent>
      </Card>
    </div>
  );
}
