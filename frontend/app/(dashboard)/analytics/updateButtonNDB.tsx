import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { retrain_ndb, stop_workflow } from '@/lib/backend';
import { useRouter, useSearchParams } from 'next/navigation';

function generateTimestamp(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${year}${month}${day}_${hours}${minutes}${seconds}`;
}

interface UpdateButtonProps {
  modelName: string;
}

export default function UpdateButton({ modelName }: UpdateButtonProps) {
  const params = useSearchParams();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Extract parameters from URL
  const workflowId = params.get('id');
  const username = params.get('username');
  const old_model_id = params.get('old_model_id');

  const handleUpdate = async () => {
    if (!workflowId || !username || !modelName || !old_model_id) {
      setError('Missing required parameters');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);

    const base_model_identifier = `${username}/${modelName}`;
    const timestamp = generateTimestamp();
    const new_model_name = `${modelName}_${timestamp}`;

    const job_options = {
      allocation_cores: 4,
      allocation_memory: 8192,
    };

    try {
      // Stop the existing workflow
      await stop_workflow(username, modelName);

      // Initiate retraining with new model name
      const retrainParams = {
        model_name: new_model_name,
        base_model_identifier: base_model_identifier,
        job_options: job_options,
      };
      await retrain_ndb(retrainParams);

      setSuccess(true);
    } catch (err: any) {
      console.error('Error during update:', err);
      setError(err.message || 'An error occurred during the update process');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center space-y-4 my-8">
      <Button
        onClick={handleUpdate}
        disabled={loading}
        className="w-64"
        variant={success ? 'secondary' : 'default'}
      >
        {loading ? 'Updating...' : success ? 'Update Successful!' : 'Update model with feedback'}
      </Button>

      {error && <p className="text-red-500 text-center mt-2">{error}</p>}

      {success && (
        <p className="text-green-500 text-center mt-2">
          Model update process initiated successfully. This may take some time to complete.
        </p>
      )}
    </div>
  );
}
