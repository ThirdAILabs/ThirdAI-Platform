import Link from 'next/link';
import { useEffect, useState } from 'react';

import Image from 'next/image';
import { Badge } from '@/components/ui/badge';
import { Button } from '@mui/material';
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
  start_workflow,
  stop_workflow,
  delete_workflow,
} from '@/lib/backend';
import { useRouter } from 'next/navigation';
import { Modal } from '@/components/ui/Modal';
import { InformationCircleIcon } from '@heroicons/react/solid';

enum DeployStatus {
  None = "",
  TrainingFailed = "Training failed",
  Training = "Training",
  Inactive = "Inactive",
  Starting = "Starting",
  Active = "Active",
  Failed = "Failed",
};

export function WorkFlow({ workflow }: { workflow: Workflow }) {
  const router = useRouter();
  const [deployStatus, setDeployStatus] = useState<DeployStatus>(DeployStatus.None);
  const [deployType, setDeployType] = useState<string>('');

  function goToEndpoint() {
    switch (workflow.type) {
      case 'ndb': {
        // TODO don't use url params
        if (workflow.genai_provider) {
          const genAiProvider = `${workflow.genai_provider}`;
          const ifGenerationOn = true;
          const newUrl = `/semantic-search/${workflow.model_id}?workflowId=${workflow.model_id}&ifGenerationOn=${ifGenerationOn}&genAiProvider=${genAiProvider}`;
          window.open(newUrl, '_blank');
        } else {
          const ifGenerationOn = false;
          const newUrl = `/semantic-search/${workflow.model_id}?workflowId=${workflow.model_id}&ifGenerationOn=${ifGenerationOn}`;
          window.open(newUrl, '_blank');
        }
        break;
      }
      case 'udt': {
        const prefix =
          workflow.sub_type === 'token'
            ? '/token-classification'
            : '/text-classification';
        window.open(`${prefix}/${workflow.model_id}`, '_blank');
        break;
      }
      default:
        throw new Error(`Invalid workflow type ${workflow.type}`);
        break;
    }
  }

  function getButtonValue(status: DeployStatus): string {
    switch (status) {
      case DeployStatus.TrainingFailed:
        return "Training failed";
      case DeployStatus.Training:
        return "Training...";
      case DeployStatus.Inactive:
        return "Start";
      case DeployStatus.Starting:
        return "Starting...";
      case DeployStatus.Active:
        return "Endpoint";
      case DeployStatus.Failed:
        return "Failed";
      default:
        return "-"
    }
  }

  const handleDeploy = async () => {
    if (deployStatus == DeployStatus.Inactive) {
      setDeployStatus(DeployStatus.Starting);
      try {
        await start_workflow(workflow.username, workflow.model_name);
      } catch (e) {
        console.error('Failed to start workflow.', e);
      }
    }
  };

  useEffect(() => {
    if (workflow.train_status === "failed") {
      setDeployStatus(DeployStatus.TrainingFailed);
    } else if (workflow.train_status !== "complete") {
      setDeployStatus(DeployStatus.Training);
    } else if (workflow.deploy_status === "failed") {
      setDeployStatus(DeployStatus.Failed);
    } else if (workflow.deploy_status === "starting") {
      setDeployStatus(DeployStatus.Starting);
    } else if (workflow.deploy_status === "not_started" || workflow.deploy_status === 'stopped') {
      setDeployStatus(DeployStatus.Inactive);
    } else if (workflow.deploy_status === "complete") {
      setDeployStatus(DeployStatus.Active);
    }
  }, [workflow.train_status, workflow.deploy_status, deployStatus]);

  useEffect(() => {
    if (workflow.type === 'ndb') {
      if (workflow.default_mode && workflow.default_mode == "chat") {
        setDeployType("Chatbot")
      } else {
        setDeployType("Enterprise Search")
      }
    } else if (workflow.type === 'udt') {
      setDeployType('Natural Language Processing');
    } else if (workflow.type === 'enterprise-search') {
      setDeployType("Enterprise Search & Summarizer")
    }
  }, [workflow.type]);

  const getBadgeColor = (status: DeployStatus) => {
    switch (status) {
      case DeployStatus.Active:
        return 'bg-green-500 text-white'; // Green for good status
      case DeployStatus.Starting:
        return 'bg-yellow-500 text-white'; // Yellow for in-progress status
      case DeployStatus.Inactive:
        return 'bg-gray-500 text-white'; // Gray for inactive status
      case DeployStatus.Training:
        return 'bg-blue-500 text-white';
      case DeployStatus.TrainingFailed: // New case for training failed
        return 'bg-red-500 text-white';
      case DeployStatus.Failed:
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
      <TableCell className="font-medium text-center">{workflow.model_name}</TableCell>
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
          variant="contained"
          style={{ width: '100px' }}
          disabled={
            deployStatus != DeployStatus.Active && deployStatus != DeployStatus.Inactive
          }
        >
          {getButtonValue(deployStatus)}
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
            {deployStatus === DeployStatus.Active && (
              <>
                <DropdownMenuItem>
                  <form>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          const response = await stop_workflow(workflow.username, workflow.model_name);
                          console.log('Workflow undeployed successfully:', response);
                          // Optionally, update the UI state to reflect the undeployment
                          setDeployStatus(DeployStatus.Inactive);
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
              </>
            )}
            <DropdownMenuItem>
              <form>
                <button
                  type="button"
                  onClick={async () => {
                    if (window.confirm('Are you sure you want to delete this workflow?')) {
                      try {
                        const response = await delete_workflow(workflow.username, workflow.model_name);
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

            {workflow.type === "ndb" && (
              <Link
                href={`/analytics?id=${encodeURIComponent(workflow.model_id)}&username=${encodeURIComponent(workflow.username)}&model_name=${encodeURIComponent(workflow.model_name)}&old_model_id=${encodeURIComponent(workflow.model_id)}`}
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
                  {/* {workflow.models.map((model, index) => (
                    <tr key={index} className="hover:bg-gray-100">
                      <td className="border px-4 py-2">{model.model_name}</td>
                      <td className="border px-4 py-2">{formatBytesToMB(model.size)}</td>
                      <td className="border px-4 py-2">{formatBytesToMB(model.size_in_memory)}</td>
                    </tr>
                  ))} */}
                  {/* {workflow.models.map((model, index) => ( */}
                    <tr className="hover:bg-gray-100">
                      <td className="border px-4 py-2">{workflow.model_name}</td>
                      <td className="border px-4 py-2">{formatBytesToMB(workflow.size)}</td>
                      <td className="border px-4 py-2">{formatBytesToMB(workflow.size_in_memory)}</td>
                    </tr>
                  {/* ))} */}
                </tbody>
              </table>
            </div>
          </div>
        </Modal>
      )}
    </TableRow>
  );
}
