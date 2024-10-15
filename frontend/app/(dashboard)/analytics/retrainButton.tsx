import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { retrainNER } from '@/lib/backend';

interface RetrainButtonProps {
  modelName: string;
  username: string;
}

export default function RetrainButton({ modelName, username }: RetrainButtonProps) {
  const [newModelName, setNewModelName] = useState('');
  const [isRetraining, setIsRetraining] = useState(false);
  const [retrainError, setRetrainError] = useState('');

  const handleCreateNewModel = async () => {
    if (!newModelName) {
      setRetrainError('Please enter a name for the new model');
      return;
    }

    setIsRetraining(true);
    setRetrainError('');

    try {
      await retrainNER({
        model_name: newModelName,
        base_model_identifier: `${username}/${modelName}`,
      });
      console.log('New model created successfully');
      setNewModelName(''); // Clear the input after successful creation
    } catch (error) {
      setRetrainError(error instanceof Error ? error.message : 'An error occurred while creating the new model');
    } finally {
      setIsRetraining(false);
    }
  };

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex space-x-4">
        <Input
          type="text"
          placeholder="New model name"
          value={newModelName}
          onChange={(e) => setNewModelName(e.target.value)}
          className="w-64"
        />
        <Button onClick={handleCreateNewModel} disabled={isRetraining}>
          Create new model with feedback
        </Button>
      </div>
      {isRetraining && <p className="text-blue-500">Creating new model...</p>}
      {retrainError && <p className="text-red-500">{retrainError}</p>}
    </div>
  );
}