import Link from 'next/link';
import { useEffect, useState } from 'react';

import Image from 'next/image';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { MoreHorizontal } from 'lucide-react';
import { TableCell, TableRow } from '@/components/ui/table';
import { Workflow, validate_workflow, start_workflow, stop_workflow, delete_workflow,
        WorkflowModel, getDeployStatus
 } from '@/lib/backend';
import { useRouter } from 'next/navigation';
import { Modal } from '@/components/ui/Modal'
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
      case "semantic_search": {
        let ifGenerationOn = false; // false if semantic search, true if RAG
        const newUrl = `/semantic-search/${workflow.id}?workflowId=${workflow.id}&ifGenerationOn=${ifGenerationOn}`;
        window.open(newUrl, '_blank');
        break;
      }
      case "nlp": {
        const newUrl = `/token-classification/${workflow.id}`;
        window.open(newUrl, '_blank');
        break;
      }
      case "rag": {
        let ifGenerationOn = true; // false if semantic search, true if RAG
        const genAiProvider = `${workflow.gen_ai_provider}`;
        // TODO don't use url params
        const newUrl = `/semantic-search/${workflow.id}?workflowId=${workflow.id}&ifGenerationOn=${ifGenerationOn}&genAiProvider=${genAiProvider}`;
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
        setDeployStatus('Starting')
        console.error('Validation failed.', e);
      }
    };

    // Call the validation function immediately
    validateWorkflow();

    const validateInterval = setInterval(validateWorkflow, 3000); // Adjust the interval as needed

    return () => clearInterval(validateInterval);
  }, [workflow.id]);

  const handleDeploy = async () => {
    try {
      if (isValid) {
        setDeployStatus('Starting'); // set to starting because user intends to start workflow
        await start_workflow(workflow.id);
      }
    } catch (e) {
      setDeployStatus('Starting'); // set to starting because user intends to start workflow
      console.error('Failed to start workflow.', e);
    }
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
          if (deployStatus == 'Starting') {
            console.log('user previously specified they want to start workflow, automatically deploy model.')
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
      } else if (allComplete) {
        setDeployStatus('Active'); // Models are complete and workflow is active
      } else if (deployStatus !== 'Starting') {
        // if user hasn't chosen to start the workflow, we want to set it to Inactive
        setDeployStatus('Inactive');
      }
    } else {
      // If no models are present, the workflow is ready to deploy
      setDeployStatus('Error: Underlying model not present');
    }
  }, [workflow.models, workflow.status, deployStatus]);

  useEffect(()=>{
    if (workflow.type === 'semantic_search') {
      setDeployType('Semantic Search')
    } else if (workflow.type === 'nlp') {
      setDeployType('Natural Language Processing')
    } else if (workflow.type === 'rag') {
      setDeployType('Retrieval Augmented Generation')
    }
  },[workflow.type])

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

  return (
    <TableRow>
      <TableCell className="hidden sm:table-cell">
        <Image
          alt="workflow image"
          className="aspect-square rounded-md object-cover"
          height="64"
          src={'/thirdai-small.png'}
          width="64"
        />
      </TableCell>
      <TableCell className="font-medium text-center">{workflow.name}</TableCell>
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
          onClick={deployStatus === 'Active' ? goToEndpoint : handleDeploy}
          className="text-white focus:ring-4 focus:outline-none font-medium text-sm p-2.5 text-center inline-flex items-center me-2"
          style={{ width: '100px' }}
          disabled={isTrainingIncomplete || ['Failed', 'Starting', 'Error: Underlying model not present', 'Training failed'].includes(deployStatus)}
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
        <button 
          onClick={toggleModal} 
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          <InformationCircleIcon className="h-6 w-6" />
        </button>
      </TableCell>
      <TableCell className='text-center font-medium'>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button aria-haspopup="true" size="icon" variant="ghost">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">Toggle menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem>Edit</DropdownMenuItem>
            {
              deployStatus === 'Active'
              &&
              <>
              <DropdownMenuItem>
                <form>
                  <button type="button"
                    onClick={async () => {
                      try {
                        const response = await stop_workflow(workflow.id);
                        console.log('Workflow undeployed successfully:', response);
                        // Optionally, update the UI state to reflect the undeployment
                        setDeployStatus('Inactive');
                      } catch (error) {
                        console.error('Error undeploying workflow:', error);
                        alert('Error undeploying workflow:' + error)
                      }
                    }}
                  >
                    Stop App
                  </button>
                </form>
              </DropdownMenuItem>
              </>
            }
            <DropdownMenuItem>
              <form>
                <button type="button"
                  onClick={async () => {
                    if (window.confirm('Are you sure you want to delete this workflow?')) {
                      try {
                        const response = await delete_workflow(workflow.id);
                        console.log('Workflow deleted successfully:', response);
                      } catch (error) {
                        console.error('Error deleting workflow:', error);
                        alert('Error deleting workflow:' + error)
                      }
                    }
                  }}
                >
                  Delete App
                </button>
              </form>
            </DropdownMenuItem>
            <Link href={`/analytics?id=${encodeURIComponent(`${workflow.id}`)}`}>
              <DropdownMenuItem>
                  <button type="button">Usage stats</button>
              </DropdownMenuItem>
            </Link>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>

      {/* Modal for displaying model details */}
      {showModal && (
        <Modal onClose={toggleModal}>
          <div className="p-4">
            <h2 className="text-lg font-bold mb-4">App Details</h2>
            {workflow.models.map((model, index) => (
              <div key={index} className="mb-4">
                <p><strong>Model Name:</strong> {model.model_name}</p>
                <p><strong>Size on Disk:</strong> {formatBytesToMB(model.size)}</p>
                <p><strong>Size in Memory:</strong> {formatBytesToMB(model.size_in_memory)}</p>

                {/* Button for viewing model status in Grafana */}
                <ModelStatusButton model={model} />
              </div>
            ))}
          </div>
        </Modal>
      )}
    </TableRow>
  );
}

interface ModelStatusButtonProps {
  model: WorkflowModel;
}

interface GetDeployStatusResponse {
  model_id: string;
  deploy_status: string;
  weblink?: string;  // Optional since it might not always be present
}

const ModelStatusButton: React.FC<ModelStatusButtonProps> = ({ model }) => {
  const [weblink, setWeblink] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [deployStatus, setDeployStatus] = useState<string>(model.deploy_status);

  useEffect(() => {
    // Fetch the deploy status and weblink
    getDeployStatus({
      deployment_identifier: `${model.model_id}:${model.model_id}`,
      model_identifier: `${model.username}/${model.model_name}`,
    })
      .then((response: { data: GetDeployStatusResponse }) => {
        setDeployStatus(response.data.deploy_status);

        // Set weblink if available
        if (response.data.weblink) {
          console.log('weblink i got', response.data.weblink)
          setWeblink(response.data.weblink);
        }

        setLoading(false);
      })
      .catch((error) => {
        console.error('Error fetching deployment status:', error);
        setLoading(false);
      });
  }, [model]);

  return (
    <div className="mt-2">
      {loading ? (
        <p>Loading status...</p>
      ) : deployStatus === 'complete' && weblink ? (
        <a
          href={weblink}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          View Model Status
        </a>
      ) : (
        <button
          disabled
          className="px-4 py-2 bg-gray-300 text-gray-700 rounded"
        >
          Model not deployed
        </button>
      )}
    </div>
  );
};
