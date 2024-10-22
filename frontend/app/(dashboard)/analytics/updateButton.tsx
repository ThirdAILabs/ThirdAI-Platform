import React, { useState } from 'react';
import { Button } from '@mui/material';
import { retrainTokenClassifier } from '@/lib/backend';

interface UpdateButtonProps {
  modelName: string;
}

interface UpdateResponse {
  status: string;
  message: string;
  data: {
    model_id: string;
    user_id: string;
  };
}

export default function UpdateButton({ modelName }: UpdateButtonProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState('');
  const [initiateUpdateSuccess, setInitiateUpdateSuccess] = useState(false);

  const handleUpdateModel = async () => {
    setIsUpdating(true);
    setUpdateError('');
    setInitiateUpdateSuccess(false);

    try {
      const response: UpdateResponse = await retrainTokenClassifier({ model_name: modelName });
      if (response.status === 'success') {
        setInitiateUpdateSuccess(true);
        console.log('Model update initiated successfully:', response.message);
      } else {
        throw new Error(response.message || 'Failed to initiate update');
      }
    } catch (error) {
      setUpdateError(
        error instanceof Error
          ? error.message
          : 'An error occurred while initiating the model update'
      );
    } finally {
      setIsUpdating(false);
    }
  };

  const getButtonText = () => {
    if (isUpdating) return 'Initiating Update...';
    if (initiateUpdateSuccess) return 'Update Initiated!';
    return 'Update Existing Model';
  };

  const getButtonColor = () => {
    if (initiateUpdateSuccess) return 'success';
    return 'primary';
  };

  return (
    <div className="flex flex-col items-center space-y-4 mt-6">
      <Button
        onClick={handleUpdateModel}
        disabled={isUpdating}
        variant="contained"
        style={{ width: '200px' }}
        color={getButtonColor()}
      >
        {getButtonText()}
      </Button>
      {updateError && <p className="text-red-500">{updateError}</p>}
      {initiateUpdateSuccess && (
        <div className="text-green-500">
          <p>Update process initiated successfully. This may take some time to complete.</p>
        </div>
      )}
    </div>
  );
}
