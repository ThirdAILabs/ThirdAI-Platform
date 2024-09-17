'use client';

import { Button } from '@/components/ui/button';
import { updateModel } from '@/lib/backend';
import { useRouter, useSearchParams } from 'next/navigation';

export default function UpdateButton() {
  const params = useSearchParams();
  const router = useRouter();

  function handleUpdate() {
    updateModel(params.get('id') as string);
    router.push(`/analytics?id=${encodeURIComponent(params.get('id') + '-updated')}`);
  }

  return (
    <div
      style={{ display: 'flex', justifyContent: 'center', marginTop: '20px', marginBottom: '20vh' }}
    >
      <Button onClick={handleUpdate}>Update model with feedback</Button>
    </div>
  );
}
