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
import { SelectModel } from '@/lib/db';
import { deleteModel } from './actions';
import { deployModel, getDeployStatus, stopDeploy, getAccessToken, thirdaiPlatformBaseUrl } from '@/lib/backend';
import { useRouter } from 'next/navigation';

export function Model({ model }: { model: SelectModel }) {
  const router = useRouter();
  const [deployStatus, setDeployStatus] = useState<string>('');
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [deploymentIdentifier, setDeploymentIdentifier] = useState<string | null>(null);

  useEffect(() => {
    const username = model.username;
    const modelIdentifier = `${username}/${model.model_name}`;
    setDeploymentIdentifier(`${modelIdentifier}:${username}/${model.model_name}`)
  }, [])

  useEffect(() => {
    if (deploymentIdentifier) {
      const fetchDeployStatus = () => {
        getDeployStatus({ deployment_identifier: deploymentIdentifier })
          .then((response) => {
            console.log('Deployment status response:', response);
            if (response.data.deployment_id && response.data.status === 'complete') {
              setDeployStatus('Deployed');
              setDeploymentId(response.data.deployment_id);
            } else if (response.data.status === 'in_progress') {
              setDeployStatus('Deploying');
            } else {
              setDeployStatus('Ready to Deploy');
            }
          })
          .catch((error) => {
            if (error.response && error.response.status === 400) {
              console.log('Model is not deployed.');
              setDeployStatus('Ready to Deploy');
            } else {
              console.error('Error fetching deployment status:', error);
            }
          });
      };

      fetchDeployStatus(); // Initial fetch

      const intervalId = setInterval(fetchDeployStatus, 2000); // Fetch every 2 seconds

      // Cleanup interval on component unmount
      return () => clearInterval(intervalId);
    }
  }, [deploymentIdentifier]);

  function goToEndpoint() {
    switch (model.type) {
      case "ndb":
        const accessToken = getAccessToken();
        let ifGenerationOn = false; // false if semantic search, true if RAG
        let ifGuardRailOn = false; // enable based on actual config
        let guardRailEndpoint = '...' // change based on actual config
        const newUrl = `${thirdaiPlatformBaseUrl}/search?id=${deploymentId}&token=${accessToken}&ifGenerationOn=${ifGenerationOn}&ifGuardRailOn=${ifGuardRailOn}&guardRailEndpoint=${guardRailEndpoint}`;
        window.open(newUrl, '_blank');
        break;
      case "udt":
        router.push(`/token-classification/${deploymentId}`);
        break;
      default:
        throw new Error(`Invalid model type ${model.type}`);
        break;
    }
  }

  return (
    <TableRow>
      <TableCell className="hidden sm:table-cell">
        <Image
          alt="Model image"
          className="aspect-square rounded-md object-cover"
          height="64"
          src={'/thirdai-small.png'}
          width="64"
        />
      </TableCell>
      <TableCell className="font-medium">{model.model_name}</TableCell>
      <TableCell>
        <Badge variant="outline" className="capitalize">
          {deployStatus}
          
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell">{model.type}</TableCell>
      <TableCell className="hidden md:table-cell">
        {
          model.publish_date
          ? new Date(model.publish_date).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })
          : 'N/A'
      }
      </TableCell>
      <TableCell className="hidden md:table-cell">'N\A'</TableCell>
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
        <button type="button" 
                onClick={()=>{
                  const username = model.username;
                  const modelIdentifier = `${username}/${model.model_name}`;

                  deployModel({ deployment_name: model.model_name, model_identifier: modelIdentifier, 
                    use_llm_guardrail: true,
                   })
                    .then((response) => {
                      if(response.status === 'success') {
                        console.log('deployment success')

                        setDeployStatus('Deployed')
                        setDeploymentId(response.data.deployment_id)
  
                        const modelIdentifier = `${username}/${model.model_name}`;
                        setDeploymentIdentifier(`${modelIdentifier}:${username}/${model.model_name}`)
                      }

                    })
                    .catch((error) => {
                      console.error('Error deploying model:', error);
                    });

                }}
                className="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-full text-sm p-2.5 text-center inline-flex items-center me-2 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800">
          <svg className="w-4 h-4" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 14 10">
          <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M1 5h12m0 0L9 1m4 4L9 9"/>
          </svg>
          <span className="sr-only">Deploy</span>
        </button>
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
            {
              deployStatus === 'Deployed' && deploymentIdentifier
              &&
              <DropdownMenuItem>
                <form action={deleteModel}>
                  <button type="button"
                  onClick={()=>{
                    stopDeploy({ deployment_identifier: deploymentIdentifier })
                      .then((response) => {
                        // Handle success, e.g., display a message or update the UI
                        console.log("Deployment stopped successfully:", response);
                        // Add any additional success handling logic here
                        if (response.status === 'success') {
                          setDeployStatus('Read to Deploy')
                          setDeploymentId(null)
                          setDeploymentIdentifier(null)
                        }
                      })
                      .catch((error) => {
                        // Handle error, e.g., display an error message
                        console.error("Failed to stop deployment:", error);
                        // Add any additional error handling logic here
                      });
                  }}
                  >Undeploy</button>
                </form>
              </DropdownMenuItem>
            }
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}
