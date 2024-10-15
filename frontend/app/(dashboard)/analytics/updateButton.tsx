import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { retrainNER } from '@/lib/backend';

interface UpdateButtonProps {
  modelName: string;
}

export default function UpdateButton({ modelName }: UpdateButtonProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState('');

  const handleUpdateModel = async () => {
    setIsUpdating(true);
    setUpdateError('');

    try {
      await retrainNER({ model_name: modelName });
      console.log('Model updated successfully');
    } catch (error) {
      setUpdateError(
        error instanceof Error ? error.message : 'An error occurred while updating the model'
      );
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="flex flex-col items-center space-y-4 mt-6">
      <Button onClick={handleUpdateModel} disabled={isUpdating} className="w-full max-w-md">
        Update Existing Model
      </Button>
      {isUpdating && <p className="text-blue-500">Updating model...</p>}
      {updateError && <p className="text-red-500">{updateError}</p>}
    </div>
  );
}
