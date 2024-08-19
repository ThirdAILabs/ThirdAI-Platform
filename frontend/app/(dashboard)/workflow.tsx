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
import { Workflow, validate_workflow, start_workflow, stop_workflow } from '@/lib/backend';
import { useRouter } from 'next/navigation';

export function WorkFlow({ workflow }: { workflow: Workflow }) {
  const router = useRouter();
  const [deployStatus, setDeployStatus] = useState<string>('');
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
        router.push(`/token-classification/${workflow.id}`);
        break;
      }
      case "rag": {
        let ifGenerationOn = true; // false if semantic search, true if RAG
        const newUrl = `/semantic-search/${workflow.id}?workflowId=${workflow.id}&ifGenerationOn=${ifGenerationOn}`;
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
    const validateInterval = setInterval(async () => {
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
        console.error('Validation failed.', e);
      }
    }, 3000); // Adjust the interval as needed, e.g., every 5 seconds

    return () => clearInterval(validateInterval);
  }, [workflow.id]);

  const handleDeploy = async () => {
    try {
      if (isValid) {
        await start_workflow(workflow.id);
      } else {
        alert('Cannot deploy. The workflow is not valid.');
      }
    } catch (e) {
      console.error('Failed to start workflow.', e);
      alert('Failed to start the workflow.');
    }
  };

  useEffect(() => {
    if (workflow.status === 'inactive') {
      // If the workflow is inactive, we always say it's inactive regardless of model statuses
      setDeployStatus('Inactive');
    } else if (workflow.models && workflow.models.length > 0) {
      let hasFailed = false;
      let isInProgress = false;
      let allComplete = true;
  
      for (const model of workflow.models) {
        if (model.deploy_status === 'failed') {
          hasFailed = true;
          break; // If any model has failed, no need to check further
        } else if (model.deploy_status === 'in_progress') {
          isInProgress = true;
          allComplete = false; // If any model is in progress, not all can be complete
        } else if (model.deploy_status !== 'complete') {
          allComplete = false; // If any model is not complete, mark allComplete as false
        }
      }
  
      if (hasFailed) {
        setDeployStatus('Failed');
      } else if (isInProgress) {
        setDeployStatus('Starting');
      } else if (allComplete) {
        setDeployStatus('Active'); // Models are complete and workflow is active
      } else {
        setDeployStatus('Ready to Start');
      }
    } else {
      // If no models are present, the workflow is ready to deploy
      setDeployStatus('Ready to Start');
    }
  }, [workflow.models, workflow.status]);

  useEffect(()=>{
    if (workflow.type === 'semantic_search') {
      setDeployType('Semantic Search')
    } else if (workflow.type === 'nlp') {
      setDeployType('Natural Language Processing')
    } else if (workflow.type === 'rag') {
      setDeployType('Retrieval Augmented Generation')
    }
  },[workflow.type])


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
      <TableCell className="font-medium">{workflow.name}</TableCell>
      <TableCell>
        <Badge variant="outline" className="capitalize">
          {deployStatus}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell">{deployType}</TableCell>
      <TableCell className="hidden md:table-cell">
        {
          new Date(workflow.publish_date).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })
        }
      </TableCell>
      <TableCell className="hidden md:table-cell">&apos;N\A&apos;</TableCell>
      <TableCell className="hidden md:table-cell">
        <button type="button" 
                onClick={goToEndpoint}
                className="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-full text-sm p-2.5 text-center inline-flex items-center me-2 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800">
          <svg className="w-4 h-4" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 14 10">
          <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M1 5h12m0 0L9 1m4 4L9 9"/>
          </svg>
          <span className="sr-only">Go to endpoint</span>
        </button>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        {
          isValid
          &&
          <button type="button" 
                  onClick={handleDeploy}
                  className="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-full text-sm p-2.5 text-center inline-flex items-center me-2 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800">
            <svg className="w-4 h-4" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 14 10">
              <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M1 5h12m0 0L9 1m4 4L9 9"/>
            </svg>
            <span className="sr-only">Deploy</span>
          </button>
        }
      </TableCell>
      <TableCell>
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
            <Link href={`/analytics?id=${encodeURIComponent(`${workflow.id}`)}`}>
                <DropdownMenuItem>
                    <button type="button">Usage stats</button>
                </DropdownMenuItem>
              </Link>
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
                      }
                    }}
                  >
                    Stop Workflow
                  </button>
                </form>
              </DropdownMenuItem>
              </>
            }
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}
