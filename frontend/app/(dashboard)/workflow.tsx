import Link from 'next/link';
import { AlertCircle } from 'lucide-react';
import React, { useContext, useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button, RadioGroup, Radio, Tooltip } from '@mui/material';
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
  getTrainingStatus,
  getDeployStatus,
  getTrainingLogs,
  getDeploymentLogs,
} from '@/lib/backend';
import { Modal } from '@/components/ui/Modal';
import { InformationCircleIcon } from '@heroicons/react/solid';
import { Model, getModels } from '@/utils/apiRequests';
import { UserContext } from '../user_wrapper';
import { ContentCopy, Download } from '@mui/icons-material'; // MUI icons instead of SVG paths
import { ExpandMore, ChevronRight } from '@mui/icons-material';

enum DeployStatus {
  None = '',
  TrainingFailed = 'Training failed',
  Training = 'Training',
  Inactive = 'Inactive',
  Starting = 'Starting',
  Active = 'Active',
  Failed = 'Failed',
}

enum DeployMode {
  Dev = 'Dev',
  Production = 'Production',
}

interface ErrorState {
  type: 'training' | 'deployment';
  messages: string[];
}

interface WarningState {
  type: 'training' | 'deployment';
  messages: string[];
}

export function WorkFlow({
  workflow,
  Workflows,
  allowActions,
  level,
}: {
  workflow: Workflow;
  Workflows: Workflow[];
  allowActions: boolean;
  level: number;
}) {
  const { user } = useContext(UserContext);
  const [deployStatus, setDeployStatus] = useState<DeployStatus>(DeployStatus.None);
  const [deployType, setDeployType] = useState<string>('');
  const [modelOwner, setModelOwner] = useState<{ [key: string]: string }>({});
  const [selectedMode, setSelectedMode] = useState<DeployMode>(DeployMode.Dev);
  const [showDeploymentModal, setShowDeploymentModal] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(true);
  const toggleCollapseIcon = () => {
    setIsCollapsed(!isCollapsed);
  };
  useEffect(() => {
    getModelsData();
  }, []);

  async function getModelsData() {
    const modelData = await getModels();
    const tempModelOwner: { [key: string]: string } = {}; // TypeScript object to store name as key and owner as value
    if (modelData) {
      for (let index = 0; index < modelData.length; index++) {
        const name = modelData[index].name;
        const owner = modelData[index].owner;
        tempModelOwner[name] = owner;
      }
    }
    setModelOwner(tempModelOwner);
  }
  function goToEndpoint() {
    switch (workflow.type) {
      case 'enterprise-search': {
        // enterprise-search is rag with generation

        // TODO don't use url params
        const llmProvider = `${workflow.attributes.llm_provider}`;
        const ifGenerationOn = true;
        const chatMode = workflow.attributes.default_mode == 'chat';
        const newUrl = `/semantic-search/${workflow.model_id}?workflowId=${workflow.model_id}&ifGenerationOn=${ifGenerationOn}&genAiProvider=${llmProvider}&chatMode=${chatMode}`;
        window.open(newUrl, '_blank');
        break;
      }
      case 'ndb': {
        // ndb is is rag without generation
        const llmProvider = workflow.attributes.llm_provider
          ? workflow.attributes.llm_provider
          : null;
        // TODO don't use url params
        const ifGenerationOn = llmProvider != null;
        const newUrl = `/semantic-search/${workflow.model_id}?workflowId=${workflow.model_id}&ifGenerationOn=${ifGenerationOn}&genAiProvider=${llmProvider}`;
        window.open(newUrl, '_blank');
        break;
      }
      case 'udt': {
        const prefix =
          workflow.sub_type === 'token' ? '/token-classification' : '/text-classification';
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
        return 'Training failed';
      case DeployStatus.Training:
        return 'Training...';
      case DeployStatus.Inactive:
        return 'Start';
      case DeployStatus.Starting:
        return 'Starting...';
      case DeployStatus.Active:
        return 'Endpoint';
      case DeployStatus.Failed:
        return 'Failed';
      default:
        return '-';
    }
  }

  const handleStartWorkflow = () => {
    if (deployStatus === DeployStatus.Active) {
      goToEndpoint();
    } else if (workflow.type === 'ndb' || workflow.type === 'enterprise-search') {
      setShowDeploymentModal(true);
    } else {
      handleDeploy(null); // For 'udt' type, start directly without mode selection
    }
  };

  const handleDeploy = async (mode: DeployMode | null = null) => {
    if (deployStatus == DeployStatus.Inactive) {
      setDeployStatus(DeployStatus.Starting);
      try {
        const autoscalingEnabled = mode === DeployMode.Production;
        await start_workflow(workflow.username, workflow.model_name, autoscalingEnabled);
      } catch (e) {
        console.error('Failed to start workflow.', e);
      }
    }
  };

  const toggleDeploymentModal = () => {
    setShowDeploymentModal(!showDeploymentModal);
  };

  const handleModeSelection = async () => {
    toggleDeploymentModal();
    await handleDeploy(selectedMode); // pass mode user chose dev vs. production
  };

  useEffect(() => {
    if (workflow.train_status === 'failed') {
      setDeployStatus(DeployStatus.TrainingFailed);
    } else if (workflow.train_status !== 'complete') {
      setDeployStatus(DeployStatus.Training);
    } else if (workflow.deploy_status === 'failed') {
      setDeployStatus(DeployStatus.Failed);
    } else if (workflow.deploy_status === 'starting') {
      setDeployStatus(DeployStatus.Starting);
    } else if (workflow.deploy_status === 'not_started' || workflow.deploy_status === 'stopped') {
      setDeployStatus(DeployStatus.Inactive);
    } else if (workflow.deploy_status === 'complete') {
      setDeployStatus(DeployStatus.Active);
    }
  }, [workflow.train_status, workflow.deploy_status, deployStatus]);

  useEffect(() => {
    if (workflow.type === 'ndb') {
      if (workflow.attributes.default_mode && workflow.attributes.default_mode == 'chat') {
        setDeployType('Chatbot');
      } else {
        setDeployType('Enterprise Search');
      }
    } else if (workflow.type === 'udt') {
      setDeployType('Natural Language Processing');
    } else if (workflow.type === 'enterprise-search') {
      setDeployType('Enterprise Search & Summarizer');
    } else if (workflow.type === 'knowledge-extraction') {
      setDeployType('Knowledge Extraction');
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

  // Add new state for error handling
  const [error, setError] = useState<ErrorState | null>(null);
  const [warning, setWarning] = useState<WarningState | null>(null);
  const [showErrorModal, setShowErrorModal] = useState(false);

  useEffect(() => {
    const fetchStatuses = async () => {
      try {
        if (workflow.username && workflow.model_name) {
          const modelIdentifier = `${workflow.username}/${workflow.model_name}`;
          const [trainStatus, deployStatus] = await Promise.all([
            getTrainingStatus(modelIdentifier),
            getDeployStatus(modelIdentifier),
          ]);

          // Check training status
          if (
            trainStatus.data.train_status === 'failed' &&
            (trainStatus.data.errors?.length > 0 || trainStatus.data.messages?.length > 0)
          ) {
            setError({
              type: 'training',
              messages: [...(trainStatus.data.errors || []), ...(trainStatus.data.messages || [])],
            });
          } else {
            setError(null);
          }

          // Check warnings separately
          if (trainStatus.data.warnings?.length > 0) {
            setWarning({
              type: 'training',
              messages: trainStatus.data.warnings,
            });
          } else {
            setWarning(null);
          }

          // Check deployment
          if (
            deployStatus.data.deploy_status === 'failed' &&
            deployStatus.data.messages?.length > 0
          ) {
            setError({
              type: 'deployment',
              messages: deployStatus.data.messages,
            });
          }
        }
      } catch (error) {
        console.error('Error fetching statuses:', error);
      }
    };

    fetchStatuses();
    const intervalId = setInterval(fetchStatuses, 2000);
    return () => clearInterval(intervalId);
  }, [workflow.username, workflow.model_name]);

  const copyContentToClipboard = () => {
    try {
      // Combine error and warning messages if they exist
      const errorMessages = error?.messages || [];
      const warningMessages = warning?.messages || [];

      // Create a formatted string with headers and messages
      let contentToCopy = '';

      if (errorMessages.length > 0) {
        contentToCopy += 'Errors:\n' + errorMessages.map((msg) => `• ${msg}`).join('\n') + '\n\n';
      }

      if (warningMessages.length > 0) {
        contentToCopy += 'Warnings:\n' + warningMessages.map((msg) => `• ${msg}`).join('\n');
      }

      // Create a temporary textarea element
      const textarea = document.createElement('textarea');
      textarea.value = contentToCopy.trim();
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.top = '0';
      document.body.appendChild(textarea);

      // Select and copy the text
      textarea.select();
      document.execCommand('copy');

      // Clean up
      document.body.removeChild(textarea);

      // Show success notification
      const toast = document.createElement('div');
      toast.className =
        'fixed bottom-4 right-4 bg-gray-800 text-white px-4 py-2 rounded-md shadow-lg z-50';
      toast.textContent = 'Content copied to clipboard';
      document.body.appendChild(toast);

      setTimeout(() => {
        document.body.removeChild(toast);
      }, 2000);
    } catch (err) {
      console.error('Failed to copy content:', err);
      // Show error notification
      const errorToast = document.createElement('div');
      errorToast.className =
        'fixed bottom-4 right-4 bg-red-600 text-white px-4 py-2 rounded-md shadow-lg z-50';
      errorToast.textContent = 'Failed to copy content';
      document.body.appendChild(errorToast);
      setTimeout(() => document.body.removeChild(errorToast), 2000);
    }
  };

  return (
    <>
      <TableRow>
        {/* Collapsible button */}
        {workflow.type === 'enterprise-search' ? (
          <TableCell className="text-center">
            <button
              onClick={() => {
                toggleCollapseIcon();
              }}
            >
              {isCollapsed ? <ChevronRight /> : <ExpandMore />}
            </button>
          </TableCell>
        ) : (
          <TableCell />
        )}

        <TableCell>
          <div className="flex items-center">
            <div style={{ marginLeft: `${level * 20}px` }} className="flex items-center">
              {level > 0 && <span className="mr-2 text-gray-400">└─</span>}
              {workflow.model_name}
            </div>
          </div>
        </TableCell>

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
            onClick={handleStartWorkflow}
            variant="contained"
            style={{ width: '100px' }}
            disabled={
              (deployStatus !== DeployStatus.Active && deployStatus !== DeployStatus.Inactive) ||
              (deployStatus === DeployStatus.Active && workflow.type === 'knowledge-extraction')
            }
          >
            {getButtonValue(deployStatus)}
          </Button>
        </TableCell>
        <TableCell className="text-center font-medium">
          {allowActions && (
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
                  <DropdownMenuItem
                    onClick={async () => {
                      try {
                        const response = await stop_workflow(
                          workflow.username,
                          workflow.model_name
                        );
                        console.log('Workflow undeployed successfully:', response);
                        // Optionally, update the UI state to reflect the undeployment
                        setDeployStatus(DeployStatus.Inactive);
                      } catch (error) {
                        console.error('Error undeploying workflow:', error);
                        alert('Error undeploying workflow:' + error);
                      }
                    }}
                  >
                    <button type="button">Stop App</button>
                  </DropdownMenuItem>
                )}

                {(modelOwner[workflow.model_name] === user?.username || user?.global_admin) && (
                  <DropdownMenuItem
                    onClick={async () => {
                      if (window.confirm('Are you sure you want to delete this workflow?')) {
                        try {
                          const response = await delete_workflow(
                            workflow.username,
                            workflow.model_name
                          );
                          console.log('Workflow deleted successfully:', response);
                        } catch (error) {
                          console.error('Error deleting workflow:', error);
                          alert('Error deleting workflow:' + error);
                        }
                      }
                    }}
                  >
                    <form>
                      <button type="button">Delete App</button>
                    </form>
                  </DropdownMenuItem>
                )}

                {workflow.type === 'enterprise-search' &&
                  (modelOwner[workflow.model_name] === user?.username || user?.global_admin) && (
                    <Link
                      href={`/analytics?id=${encodeURIComponent(workflow.model_id)}&username=${encodeURIComponent(workflow.username)}&model_name=${encodeURIComponent(workflow.model_name)}&old_model_id=${encodeURIComponent(workflow.model_id)}`}
                    >
                      <DropdownMenuItem>
                        <button type="button">Usage Dashboard</button>
                      </DropdownMenuItem>
                    </Link>
                  )}

                {workflow.type === 'udt' && (
                  <Link
                    href={`/analytics?id=${encodeURIComponent(workflow.model_id)}&username=${encodeURIComponent(workflow.username)}&model_name=${encodeURIComponent(workflow.model_name)}&old_model_id=${encodeURIComponent(workflow.model_id)}`}
                  >
                    <DropdownMenuItem>
                      <Tooltip
                        title={
                          deployStatus === DeployStatus.Failed ||
                          deployStatus === DeployStatus.TrainingFailed
                            ? 'Access restricted: model failed'
                            : ''
                        }
                        arrow
                      >
                        <span>
                          <button
                            type="button"
                            disabled={
                              deployStatus === DeployStatus.Failed ||
                              deployStatus === DeployStatus.TrainingFailed
                            }
                            style={{
                              cursor:
                                deployStatus === DeployStatus.Failed ||
                                deployStatus === DeployStatus.TrainingFailed
                                  ? 'not-allowed'
                                  : 'pointer',
                            }}
                          >
                            Usage Dashboard
                          </button>
                        </span>
                      </Tooltip>
                    </DropdownMenuItem>
                  </Link>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </TableCell>

        {/* Single TableCell for both error and warning icons */}
        <TableCell className="text-right pr-4">
          <div className="flex items-center justify-end space-x-2">
            {/* Error icon */}
            {error && (
              <Button
                variant="contained"
                color="error"
                onClick={() => setShowErrorModal(true)}
                size="small"
                sx={{
                  minWidth: 'unset',
                  padding: '8px',
                  borderRadius: '50%',
                }}
              >
                <AlertCircle className="h-5 w-5" />
              </Button>
            )}

            {/* Warning icon */}
            {warning && (
              <Button
                variant="contained"
                color="warning"
                onClick={() => setShowErrorModal(true)}
                size="small"
                sx={{
                  minWidth: 'unset',
                  padding: '8px',
                  borderRadius: '50%',
                  backgroundColor: '#f59e0b',
                  '&:hover': {
                    backgroundColor: '#d97706',
                  },
                }}
              >
                <AlertCircle className="h-5 w-5" />
              </Button>
            )}
          </div>
        </TableCell>

        {/* Error/Warning Modal */}
        {showErrorModal && (error || warning) && (
          <Modal onClose={() => setShowErrorModal(false)}>
            <div className="p-6 max-h-[80vh] flex flex-col">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">
                  {error?.type === 'training' || warning?.type === 'training'
                    ? 'Training Status'
                    : 'Deployment Status'}
                </h2>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<ContentCopy />}
                  onClick={copyContentToClipboard}
                >
                  Copy Content
                </Button>
              </div>
              <div className="flex-1 overflow-y-auto min-h-0">
                {/* Show errors if any */}
                {error && error.messages.length > 0 && (
                  <div className="space-y-2 mb-4">
                    <h3 className="font-medium text-red-600 sticky top-0 bg-white py-2">Errors:</h3>
                    <ul className="list-disc pl-5 space-y-2">
                      {error.messages.map((message, index) => (
                        <li key={index} className="text-gray-600">
                          {message}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Show warnings if any */}
                {warning && warning.messages.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="font-medium text-amber-600 sticky top-0 bg-white py-2">
                      Warnings:
                    </h3>
                    <ul className="list-disc pl-5 space-y-2">
                      {warning.messages.map((message, index) => (
                        <li key={index} className="text-gray-600">
                          {message}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </Modal>
        )}

        {/* Modal for selecting between Dev mode and Production mode */}
        {showDeploymentModal && (
          <Modal onClose={toggleDeploymentModal}>
            <div className="p-2 max-w-[200px] mx-auto">
              <h2 className="text-sm font-semibold mb-2">Choose Configuration</h2>
              <div>
                <RadioGroup
                  aria-label="mode-selection"
                  value={selectedMode}
                  onChange={(e) => setSelectedMode(e.target.value as DeployMode)}
                  className="space-y-1"
                >
                  <div className="flex items-center space-x-1">
                    <Radio value={DeployMode.Dev} size="small" />
                    <span className="text-sm">Dev</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Radio value={DeployMode.Production} size="small" />
                    <span className="text-sm">Prod</span>
                  </div>
                </RadioGroup>
                <div className="mt-2 flex justify-center">
                  <Button
                    onClick={handleModeSelection}
                    variant="contained"
                    size="small"
                    className="text-sm py-1 px-3"
                  >
                    Confirm
                  </Button>
                </div>
              </div>
            </div>
          </Modal>
        )}
      </TableRow>
      {/* Dependency models being rendered as child*/}
      {!isCollapsed &&
        workflow.dependencies?.map((dependency) => {
          return Workflows.map((thisWorkflow) => {
            if (thisWorkflow.model_id === dependency.model_id) {
              return (
                <WorkFlow
                  key={dependency.model_id}
                  workflow={thisWorkflow}
                  Workflows={Workflows}
                  allowActions={false}
                  level={1}
                />
              );
            }
          });
        })}
    </>
  );
}
