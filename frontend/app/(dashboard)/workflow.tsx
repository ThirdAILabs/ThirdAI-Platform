import Link from 'next/link';
import { useEffect, useState } from 'react';

import Image from 'next/image';
import { Badge } from '@/components/ui/badge';
import { Button, RadioGroup, Radio } from '@mui/material';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreHorizontal } from 'lucide-react';
import { TableCell, TableRow } from '@/components/ui/table';
import {
  Workflow,
  validate_workflow,
  start_workflow,
  stop_workflow,
  delete_workflow,
} from '@/lib/backend';
import { useRouter } from 'next/navigation';
import { Modal } from '@/components/ui/Modal';
import { InformationCircleIcon } from '@heroicons/react/solid';

export function WorkFlow({ workflow }: { workflow: Workflow }) {
  const router = useRouter();
  const [deployStatus, setDeployStatus] = useState<string>('');
  // Deploystatus can be one of following:
  // Inactive
  // Failed
  // Starting
  // Active
  // Starting
  // Error: Underlying model not present
  // Training failed
  // Training...
  const [isTrainingIncomplete, setIsTrainingIncomplete] = useState<boolean>(false);
  const [deployType, setDeployType] = useState<string>('');

  function goToEndpoint() {
    switch (workflow.type) {
      case 'semantic_search': {
        let ifGenerationOn = false; // false if semantic search, true if RAG
        const newUrl = `/semantic-search/${workflow.id}?workflowId=${workflow.id}&ifGenerationOn=${ifGenerationOn}`;
        window.open(newUrl, '_blank');
        break;
      }
      case 'nlp': {
        const prefix =
          workflow.models[0].sub_type === 'token'
            ? '/token-classification'
            : '/text-classification';
        window.open(`${prefix}/${workflow.id}`, '_blank');
        break;
      }
      case 'rag': {
        let ifGenerationOn = true; // false if semantic search, true if RAG
        const genAiProvider = `${workflow.gen_ai_provider}`;
        // TODO don't use url params
        const newUrl = `/semantic-search/${workflow.id}?workflowId=${workflow.id}&ifGenerationOn=${ifGenerationOn}&genAiProvider=${genAiProvider}`;
        window.open(newUrl, '_blank');
        break;
      }
      case 'chatbot': {
        let ifGenerationOn = true; // true for chatbot
        const genAiProvider = `${workflow.gen_ai_provider}`;
        const newUrl = `/semantic-search/${workflow.id}?workflowId=${workflow.id}&ifGenerationOn=${ifGenerationOn}&genAiProvider=${genAiProvider}&chatMode=true`;
        window.open(newUrl, '_blank');
        break;
      }
      default:
        throw new Error(`Invalid workflow type ${workflow.type}`);
        break;
    }
  }

  const [isValid, setIsValid] = useState(false);

  useEffect(() => {
    const validateWorkflow = async () => {
      try {
        const validationResponse = await validate_workflow(workflow.id);
        if (validationResponse.status == 'success') {
          setIsValid(true);
          console.log('Validation passed.');
        } else {
          setIsValid(false);
          console.log('Validation failed.');
        }
      } catch (e) {
        setIsValid(false);
        setDeployStatus('Starting');
        console.error('Validation failed.', e);
      }
    };

    // Call the validation function immediately
    validateWorkflow();

    const validateInterval = setInterval(validateWorkflow, 3000); // Adjust the interval as needed

    return () => clearInterval(validateInterval);
  }, [workflow.id]);

  const [selectedMode, setSelectedMode] = useState('Dev'); // Default to 'Dev' mode
  const [showDeploymentModal, setShowDeploymentModal] = useState(false); // Renamed for clarity

  const handleDeploy = async () => {
    try {
      if (isValid) {
        setDeployStatus('Starting'); // Set to starting because the user intends to start workflow
        const autoscalingEnabled = selectedMode === 'Production'; // Enable autoscaling for Production mode
        await start_workflow(workflow.id, autoscalingEnabled); // Call the API with the selected mode
      }
    } catch (e) {
      setDeployStatus('Starting'); // set to starting because user intends to start workflow
      console.error('Failed to start workflow.', e);
    }
  };

  const toggleDeploymentModal = () => {
    setShowDeploymentModal(!showDeploymentModal);
  };

  const handleModeSelection = async () => {
    toggleDeploymentModal(); // Close the modal after selection
    await handleDeploy(); // Proceed with the deploy workflow after selecting mode
  };

  useEffect(() => {
    if (workflow.models && workflow.models.length > 0) {
      let hasFailed = false;
      let isInProgress = false;
      let allComplete = true;
      let trainingIncomplete = false;
      let trainingFailed = false; // New variable to track training failure

      for (const model of workflow.models) {
        if (model.train_status === 'failed') {
          trainingFailed = true; // At least one model has a failed training status
          break; // No need to check further
        }
        if (model.train_status !== 'complete') {
          trainingIncomplete = true; // Training is still ongoing for at least one model
        }

        if (model.deploy_status === 'failed') {
          hasFailed = true;
          break; // If any model has failed deployment, no need to check further
        } else if (model.deploy_status === 'in_progress') {
          isInProgress = true;
          allComplete = false; // If any model is in progress, not all can be complete
        } else if (model.deploy_status !== 'complete') {
          allComplete = false; // If any model is not complete, mark allComplete as false

          // if user previously has specified they want to start workflow
          if (workflow.status == 'active') {
            console.log(
              'user previously specified they want to start workflow, automatically deploy model.'
            );
            handleDeploy(); // automatically deploy model
          }
        }
      }

      setIsTrainingIncomplete(trainingIncomplete);

      if (trainingFailed) {
        setDeployStatus('Training failed'); // Set the new deploy status for failed training
      } else if (trainingIncomplete) {
        setDeployStatus('Training...');
      } else if (hasFailed) {
        setDeployStatus('Failed');
      } else if (isInProgress) {
        setDeployStatus('Starting');
        return;
      } else if (workflow.status === 'inactive' && deployStatus != 'Starting') {
        // if user hasn't chosen to start the workflow, we want to set it to Inactive
        setDeployStatus('Inactive');
        return;
      } else if (allComplete) {
        setDeployStatus('Active'); // Models are complete and workflow is active
      }
    } else {
      // If no models are present, the workflow is ready to deploy
      setDeployStatus('Error: Underlying model not present');
    }
  }, [workflow.models, workflow.status, deployStatus]);

  useEffect(() => {
    if (workflow.type === 'semantic_search') {
      setDeployType('Enterprise Search');
    } else if (workflow.type === 'nlp') {
      setDeployType('Natural Language Processing');
    } else if (workflow.type === 'rag') {
      setDeployType('Enterprise Search & Summarizer');
    } else if (workflow.type === 'chatbot') {
      setDeployType('Chatbot');
    }
  }, [workflow.type]);

  const getBadgeColor = (status: string) => {
    switch (status) {
      case 'Active':
        return 'bg-green-500 text-white'; // Green for good status
      case 'Starting':
        return 'bg-yellow-500 text-white'; // Yellow for in-progress status
      case 'Inactive':
        return 'bg-gray-500 text-white'; // Gray for inactive status
      case 'Training...':
        return 'bg-blue-500 text-white';
      case 'Training failed': // New case for training failed
        return 'bg-red-500 text-white';
      case 'Failed':
      case 'Error: Underlying model not present':
        return 'bg-red-500 text-white'; // Red for error statuses
      default:
        return 'bg-gray-500 text-white'; // Default to gray if status is unknown
    }
  };

  const [showModal, setShowModal] = useState(false);

  const toggleModal = () => {
    setShowModal(!showModal);
  };

  const formatBytesToMB = (bytes: string) => {
    return (parseInt(bytes) / (1024 * 1024)).toFixed(2) + ' MB';
  };

  // Find the model where component === "search"
  const searchModel = workflow.models.find((model) => model.component === 'search');

  return (
    <TableRow>
      <TableCell className="font-bold text-center">{workflow.name}</TableCell>
      <TableCell className="text-center font-medium">
        <Badge variant="outline" className={`capitalize ${getBadgeColor(deployStatus)}`}>
          {deployStatus}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell text-center font-medium">{deployType}</TableCell>
      <TableCell className="hidden md:table-cell text-center font-medium">
        {new Date(workflow.publish_date).toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        })}
      </TableCell>
      <TableCell className="hidden md:table-cell text-center font-medium">
        <Button
          onClick={() => {
            if (deployStatus === 'Active') {
              goToEndpoint();
            } else {
              setShowDeploymentModal(true); // Show modal when Start is clicked
            }
          }}
          variant="contained"
          style={{ width: '100px' }}
          disabled={
            isTrainingIncomplete ||
            [
              'Failed',
              'Starting',
              'Error: Underlying model not present',
              'Training failed',
            ].includes(deployStatus)
          }
        >
          {deployStatus === 'Training failed' // Check explicitly for 'Training failed'
            ? 'Training Failed' // Show 'Training Failed' text
            : isTrainingIncomplete
              ? 'Training...'
              : deployStatus === 'Active'
                ? 'Endpoint'
                : deployStatus === 'Inactive'
                  ? 'Start'
                  : ['Failed', 'Error: Underlying model not present'].includes(deployStatus)
                    ? 'Start'
                    : 'Endpoint'}
        </Button>
      </TableCell>
      <TableCell className="text-center font-medium">
        <button onClick={toggleModal} className="text-gray-400 hover:text-gray-600 text-sm">
          <InformationCircleIcon className="h-6 w-6" />
        </button>
      </TableCell>
      <TableCell className="text-center font-medium">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              aria-haspopup="true"
              size="small"
              variant="text" // Using "text" as base variant
              sx={{
                color: 'inherit', // Default text color
                '&:hover': {
                  backgroundColor: 'var(--accent)', // Replace with your accent color
                  color: 'var(--accent-foreground)', // Replace with your foreground color for hover
                },
              }}
            >
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">Toggle menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            {deployStatus === 'Active' && (
              <DropdownMenuItem>
                <form>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const response = await stop_workflow(workflow.id);
                        console.log('Workflow undeployed successfully:', response);
                        // Optionally, update the UI state to reflect the undeployment
                        setDeployStatus('Inactive');
                      } catch (error) {
                        console.error('Error undeploying workflow:', error);
                        alert('Error undeploying workflow:' + error);
                      }
                    }}
                  >
                    Stop App
                  </button>
                </form>
              </DropdownMenuItem>
            )}
            <DropdownMenuItem>
              <form>
                <button
                  type="button"
                  onClick={async () => {
                    if (window.confirm('Are you sure you want to delete this workflow?')) {
                      try {
                        const response = await delete_workflow(workflow.id);
                        console.log('Workflow deleted successfully:', response);
                      } catch (error) {
                        console.error('Error deleting workflow:', error);
                        alert('Error deleting workflow:' + error);
                      }
                    }
                  }}
                >
                  Delete App
                </button>
              </form>
            </DropdownMenuItem>

            {searchModel && (
              <Link
                href={`/analytics?id=${encodeURIComponent(workflow.id)}&username=${encodeURIComponent(searchModel.username)}&model_name=${encodeURIComponent(searchModel.model_name)}&old_model_id=${encodeURIComponent(searchModel.model_id)}`}
              >
                <DropdownMenuItem>
                  <button type="button">Search usage stats</button>
                </DropdownMenuItem>
              </Link>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>

      {/* Modal for displaying model details */}
      {showModal && (
        <Modal onClose={toggleModal}>
          <div className="p-4">
            <h2 className="text-lg font-bold mb-4">App Details</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full table-auto border-collapse border border-gray-300">
                <thead>
                  <tr className="bg-gray-200">
                    <th className="border px-4 py-2 text-left">Model Name</th>
                    <th className="border px-4 py-2 text-left">Size on Disk (MB)</th>
                    <th className="border px-4 py-2 text-left">Size in Memory (MB)</th>
                  </tr>
                </thead>
                <tbody>
                  {workflow.models.map((model, index) => (
                    <tr key={index} className="hover:bg-gray-100">
                      <td className="border px-4 py-2">{model.model_name}</td>
                      <td className="border px-4 py-2">{formatBytesToMB(model.size)}</td>
                      <td className="border px-4 py-2">{formatBytesToMB(model.size_in_memory)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal for selecting between Dev mode and Production mode */}
      {showDeploymentModal && (
        <Modal onClose={toggleDeploymentModal}>
          <div className="p-4">
            <h2 className="text-lg font-bold mb-4">Choose Configuration</h2>
            <div>
              <RadioGroup
                aria-label="mode-selection"
                value={selectedMode}
                onChange={(e) => setSelectedMode(e.target.value)}
              >
                <div className="flex items-center">
                  <Radio value="Dev" />
                  <span>Dev Mode</span>
                </div>
                <div className="flex items-center">
                  <Radio value="Production" />
                  <span>Production Mode</span>
                </div>
              </RadioGroup>
              <div className="mt-4">
                <Button onClick={handleModeSelection} variant="contained">
                  Confirm
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </TableRow>
  );
}
