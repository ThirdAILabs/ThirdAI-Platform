'use client';

import { Button } from '@/components/ui/button';
import { retrain_ndb, delete_models, add_models_to_workflow, stop_workflow } from '@/lib/backend';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';

function generateTimestamp(): string {
  const now = new Date();

  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0'); // Months are zero-based
  const day = String(now.getDate()).padStart(2, '0');

  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');

  return `${year}${month}${day}_${hours}${minutes}${seconds}`;
}

export default function UpdateButton() {
  const params = useSearchParams();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEnabled, setIsEnabled] = useState(false);

  // Extract parameters from URL
  const workflowId = params.get('id');
  const username = params.get('username');
  const model_name = params.get('model_name');
  const old_model_id = params.get('old_model_id'); // Assuming you pass the old model ID

  // Effect to determine if the button should be enabled
  useEffect(() => {
    if (workflowId && username && model_name && old_model_id) {
      setIsEnabled(true);
    } else {
      setIsEnabled(false);
    }
  }, [workflowId, username, model_name, old_model_id]);

  /**
   * Handles the update button click by initiating the retrain process,
   * deleting the old model, and adding the new model to the workflow.
   */
  async function handleUpdate() {
    console.log('Update button called');

    // Validate required parameters
    if (!workflowId || !username || !model_name || !old_model_id) {
      setError('Missing required parameters: id, username, model_name, or old_model_id.');
      return;
    }

    // Define the base_model_identifier in the format 'username/model_name'
    const base_model_identifier = `${username}/${model_name}`;

    // Define job options as per your requirements
    const job_options = {
      allocation_cores: 4, // Example value
      allocation_memory: 8192, // Example value in MB
      // Add other JobOptions fields as necessary
    };

    setLoading(true);
    setError(null);

    // Generate a new model name using the current timestamp
    const timestamp = generateTimestamp();
    const new_model_name = `${model_name}_${timestamp}`;

    try {
      // Step 1: Stop the old workflow
      const stopData = await stop_workflow(workflowId);
      console.log('Workflow stopped successfully:', stopData);

      // Step 2: Retrain the model to create a new model
      const retrainParams = {
        model_name: new_model_name,
        base_model_identifier: base_model_identifier,
        job_options: job_options,
      };
      const retrainData = await retrain_ndb(retrainParams);
      console.log('Retrain initiated successfully:', retrainData);

      const new_model_id = retrainData.data.model_id; // Adjust based on backend response

      // Step 3: Delete the old model from the workflow
      const deleteParams = {
        workflow_id: workflowId,
        model_ids: [old_model_id],
        components: ['search'], // Adjust components as necessary
      };
      const deleteData = await delete_models(deleteParams);
      console.log('Old model deleted successfully:', deleteData);

      // Step 4: Add the new model to the workflow
      const addParams = {
        workflowId: workflowId,
        modelIdentifiers: [new_model_id],
        components: ['search'], // Adjust components as necessary
      };
      const addData = await add_models_to_workflow(addParams);
      console.log('New model added successfully:', addData);

      // Optionally, update the UI or navigate
      router.push(
        `/analytics?id=${encodeURIComponent(`${workflowId}-updated`)}&username=${encodeURIComponent(username)}&model_name=${encodeURIComponent(new_model_name)}`
      );
    } catch (err: any) {
      console.error('Error during the update process:', err);
      setError(err.message);
      alert('Error updating model: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  // If the button should not be enabled, do not render it
  if (!isEnabled) {
    return null; // Or render an alternative UI if desired
  }

  return (
    <div
      style={{ display: 'flex', justifyContent: 'center', marginTop: '20px', marginBottom: '20vh' }}
    >
      <Button onClick={handleUpdate} disabled={loading}>
        {loading ? 'Updating...' : 'Update model with feedback'}
      </Button>
      {error && <p style={{ color: 'red', marginTop: '10px' }}>{error}</p>}
    </div>
  );
}
