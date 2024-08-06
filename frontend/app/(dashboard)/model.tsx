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
import { deployModel, getDeployStatus, stopDeploy, getAccessToken, deploymentBaseUrl, listDeployments } from '@/lib/backend';
import { useRouter } from 'next/navigation';

export function Model({ model, pending }: { model: SelectModel, pending?: boolean }) {
  const router = useRouter();
  const [deployStatus, setDeployStatus] = useState<string>(pending ? 'in queue' :'');
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [deploymentIdentifier, setDeploymentIdentifier] = useState<string | null>(null);
  const [nerRAGEndpoint, setNerRAGEndpoint] = useState<string | null>(null);

  useEffect(() => {
    const username = model.username;
    const modelIdentifier = `${username}/${model.model_name}`;
    setDeploymentIdentifier(`${modelIdentifier}:${username}/${model.model_name}`)
  }, [])

  useEffect(() => {
    if (deploymentIdentifier) {
      const fetchDeployStatus = () => {

        if (model.type === 'rag') {
          let ndbModelId = model.ndb_model_id
          let tokenModelId = model.token_model_id

          if (ndbModelId) {
            getDeployStatus({ deployment_identifier: `${ndbModelId}:${ndbModelId}` })
            .then((response) => {
              // console.log('Deployment status response:', response);
              if (response.data.deployment_id && response.data.status === 'complete') {
                
                // console.log('The NDB model is already deployed, and deployment ID is: ', response.data.deployment_id)
                setDeploymentId(response.data.deployment_id)

                // check if NER model is deployed
                if (! tokenModelId) {
                  setDeployStatus('Deployed')
                } else {
                  getDeployStatus({ deployment_identifier: `${tokenModelId}:${tokenModelId}` })
                  .then((response) => {
                    // console.log('Deployment status response:', response);
                    if (response.data.deployment_id && response.data.status === 'complete') {
                      
                      // console.log('The NER model is already deployed, and deployment ID is: ', response.data.deployment_id)
                      setDeployStatus('Deployed')
                      
                      // Now, list deployments using the deployment_id from the response
                      listDeployments(response.data.deployment_id)
                      .then((deployments) => {
                        console.log(deployments);
                        if (deployments.length > 0) {
                            const firstDeployment = deployments[0];
                            setNerRAGEndpoint(firstDeployment.modelID);
                        }
                      })
                      .catch((error) => {
                          console.error('Error listing deployments:', error);
                      });

                    } else if (response.data.status === 'in_progress') {
      
                      // console.log('The NER model is still deploying')
                      setDeployStatus('Deploying')

                    } else {
      
                      // console.log('The NER model is not yet deployed and ready to deploy')
                      setDeployStatus('Ready to Deploy')

                    }
                  })
                  .catch((error) => {
                    if (error.response && error.response.status === 400) {
                      // console.log('The NER model is not yet deployed and ready to deploy');
                      setDeployStatus('Ready to Deploy')
                    } else {
                      console.error('Error fetching deployment status:', error);
                    }
                  });
                }

              } else if (response.data.status === 'in_progress') {

                // console.log('The NDB model is still deploying')
                setDeployStatus('Deploying')

              } else {

                // console.log('The NDB model is not yet deployed and ready to deploy')
                setDeployStatus('Ready to Deploy')
              }
            })
            .catch((error) => {
              if (error.response && error.response.status === 400) {
                // console.log('The NDB model is not yet deployed and ready to deploy');
                setDeployStatus('Ready to Deploy')
              } else {
                console.error('Error fetching deployment status:', error);
              }
            });
          }
        } else if (model.type === 'ndb' || model.type === 'udt') {
        
          getDeployStatus({ deployment_identifier: deploymentIdentifier })
            .then((response) => {
              // console.log('Deployment status response:', response);
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
                // console.log('Model is not deployed.');
                setDeployStatus('Ready to Deploy');
              } else {
                console.error('Error fetching deployment status:', error);
              }
            });
          }
      };

      fetchDeployStatus(); // Initial fetch

      const intervalId = setInterval(fetchDeployStatus, 2000); // Fetch every 2 seconds

      // Cleanup interval on component unmount
      return () => clearInterval(intervalId);
    }
  }, [deploymentIdentifier, model]);

  function goToEndpoint() {
    switch (model.type) {
      case "ndb": {
        const accessToken = getAccessToken();
        let ifGenerationOn = false; // false if semantic search, true if RAG
        let ifGuardRailOn = false; // enable based on actual config
        let guardRailEndpoint = '...' // change based on actual config
        const newUrl = `${deploymentBaseUrl}/search?id=${deploymentId}&token=${accessToken}&ifGenerationOn=${ifGenerationOn}&ifGuardRailOn=${ifGuardRailOn}&guardRailEndpoint=${guardRailEndpoint}`;
        window.open(newUrl, '_blank');
        break;
      }
      case "udt":
        router.push(`/token-classification/${deploymentId}`);
        break;
      case "rag": {
        console.log('model.use_llm_guardrail', model.use_llm_guardrail)
        console.log('nerRAGEndpoint', nerRAGEndpoint)

        if (model.use_llm_guardrail && nerRAGEndpoint) {
          const accessToken = getAccessToken();
          let ifGenerationOn = true; // false if semantic search, true if RAG
          let ifGuardRailOn = true; // enable based on actual config
          let guardRailEndpoint = nerRAGEndpoint // change based on actual config
          const newUrl = `${deploymentBaseUrl}/search?id=${deploymentId}&token=${accessToken}&ifGenerationOn=${ifGenerationOn}&ifGuardRailOn=${ifGuardRailOn}&guardRailEndpoint=${guardRailEndpoint}`;
          window.open(newUrl, '_blank');
        } else {
          const accessToken = getAccessToken();
          let ifGenerationOn = true; // false if semantic search, true if RAG
          let ifGuardRailOn = false; // enable based on actual config
          let guardRailEndpoint = '...' // change based on actual config
          const newUrl = `${deploymentBaseUrl}/search?id=${deploymentId}&token=${accessToken}&ifGenerationOn=${ifGenerationOn}&ifGuardRailOn=${ifGuardRailOn}&guardRailEndpoint=${guardRailEndpoint}`;
          window.open(newUrl, '_blank');
        }
        break
      }
      default:
        throw new Error(`Invalid model type ${model.type}`);
        break;
    }
  }

  const checkAndDeployNERModel = (tokenModelId: string | undefined) => {

      // Check and deploy NER model
      if (! tokenModelId) {
        setDeployStatus('Deployed')
      } else {
        const [tokenUsername, modelName] = tokenModelId.split('/');

        getDeployStatus({ deployment_identifier: `${tokenModelId}:${tokenModelId}` })
        .then((response) => {
          console.log('Deployment status response:', response);
          if (response.data.deployment_id && response.data.status === 'complete') {
            
            console.log('The NER model is already deployed, and deployment ID is: ', response.data.deployment_id)
            setDeployStatus('Deployed')

            // Now, list deployments using the deployment_id from the response
            listDeployments(response.data.deployment_id)
            .then((deployments) => {
              console.log(deployments);
              if (deployments.length > 0) {
                  const firstDeployment = deployments[0];
                  setNerRAGEndpoint(firstDeployment.modelID);
              }
            })
            .catch((error) => {
                console.error('Error listing deployments:', error);
            });

          } else if (response.data.status === 'in_progress') {

            console.log('The NER model is still deploying')
            setDeployStatus('Deploying')

          } else {

            console.log('The NER model is not yet deployed and ready to deploy')
            setDeployStatus('Ready to Deploy')

            deployModel({ deployment_name: modelName, model_identifier: tokenModelId })
              .then((response) => {
                if(response.status === 'success') {
                  console.log('deployment success')

                  setDeployStatus('Deployed')
                }

              })
              .catch((error) => {
                console.error('Error deploying model:', error);
              });

          }
        })
        .catch((error) => {
          if (error.response && error.response.status === 400) {
            console.log('The NER model is not yet deployed and ready to deploy');
            setDeployStatus('Deploying')

            deployModel({ deployment_name: modelName, model_identifier: tokenModelId })
              .then((response) => {
                if(response.status === 'success') {
                  console.log('deployment success')

                  setDeployStatus('Deployed')
                }

              })
              .catch((error) => {
                console.error('Error deploying model:', error);
              });
          } else {
            console.error('Error fetching deployment status:', error);
          }
        });
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

                    if (model.type === 'ndb' || model.type === 'udt') {
                        console.log('deployment_name', model.model_name)
                        console.log('modelIdentifier', modelIdentifier)


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
                    }

                    if (model.type === 'rag') {
                        let ndbModelId = model.ndb_model_id
                      
                        console.log('ndbModelId', ndbModelId)

                        if (ndbModelId) {
                          let tokenModelId = model.token_model_id

                            // Check if ndb is deployed, if not deploy it
                            getDeployStatus({ deployment_identifier: `${ndbModelId}:${ndbModelId}` })
                            .then((response) => {
                              console.log('Deployment status response:', response);
                              if (response.data.deployment_id && response.data.status === 'complete') {
                                
                                console.log('The NDB model is already deployed, and deployment ID is: ', response.data.deployment_id)
                                checkAndDeployNERModel(tokenModelId)

                                // TODO: change existing NDB model's NER model endpoint

                              } else if (response.data.status === 'in_progress') {
    
                                console.log('The NDB model is still deploying')
    
                              } else {
    
                                console.log('The NDB model is not yet deployed and ready to deploy')

                                const [username, modelName] = ndbModelId.split('/');

                                console.log('Model Identifier:', modelIdentifier);
                                console.log('modelName', modelName)

                                // deploy the ndb model
                                console.log('deploy 1', { deployment_name: modelName, model_identifier: ndbModelId, use_llm_guardrail: tokenModelId ? true : false, token_model_identifier: tokenModelId })
                                deployModel({ deployment_name: modelName, model_identifier: ndbModelId, use_llm_guardrail: tokenModelId ? true : false, token_model_identifier: tokenModelId })
                                  .then((response) => {
                                    if(response.status === 'success') {
                                      // console.log('deployment success')
                                      // setDeployStatus('Deployed')

                                      checkAndDeployNERModel(tokenModelId)
                                    }
              
                                  })
                                  .catch((error) => {
                                    console.error('Error deploying model:', error);
                                  });
    
                              }
                            })
                            .catch((error) => {
                              if (error.response && error.response.status === 400) {
                                console.log('The NDB model is not yet deployed and ready to deploy');
                                
                                const [username, modelName] = ndbModelId.split('/');

                                console.log('Model Identifier:', modelIdentifier);
                                console.log('modelName', modelName)

                                // deploy the model
                                console.log('deploy 2', { deployment_name: modelName, model_identifier: ndbModelId, use_llm_guardrail: tokenModelId ? true : false, token_model_identifier: tokenModelId })

                                deployModel({ deployment_name:modelName, model_identifier: ndbModelId, use_llm_guardrail: tokenModelId ? true : false, token_model_identifier: tokenModelId })
                                  .then((response) => {
                                    if(response.status === 'success') {
                                      // console.log('deployment success')
                                      // setDeployStatus('Deployed')

                                      checkAndDeployNERModel(tokenModelId)

                                    }
              
                                  })
                                  .catch((error) => {
                                    console.error('Error deploying model:', error);
                                  });
    
    
                              } else {
                                console.error('Error fetching deployment status:', error);
                              }
                            });
                        }

                    }

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
