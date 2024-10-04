import React, { useState, useEffect } from 'react';
import { SelectModel } from '@/lib/db';
import NERQuestions from './nlp-questions/ner-questions';
import SemanticSearchQuestions from './semantic-search-questions';
import { CardDescription } from '@/components/ui/card';
import { Button, TextField } from '@mui/material';
import { useRouter } from 'next/navigation';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import DropdownMenu from '@/components/ui/dropDownMenu';

interface RAGQuestionsProps {
  models: SelectModel[];
  workflowNames: string[];
}

const RAGQuestions = ({ models, workflowNames }: RAGQuestionsProps) => {
  const [currentStep, setCurrentStep] = useState(0);

  // Begin state variables & func for source
  const [ifUseExistingSS, setUseExistingSS] = useState<string | null>(null);
  const [existingSSmodels, setExistingSSmodels] = useState<SelectModel[]>([]);
  const [ssIdentifier, setSsIdentifier] = useState<string | null>(null);
  const [ssModelId, setSsModelId] = useState<string | null>(null);
  const [createdSS, setCreatedSS] = useState<boolean>(false);

  useEffect(() => {
    setExistingSSmodels(models.filter((model) => model.type === 'ndb'));
  }, [models]);

  // End state variables & func for source

  // Begin state variables & func for LLM guardrail

  const [ifUseLGR, setIfUseLGR] = useState('');
  const [ifUseExistingLGR, setIfUseExistingLGR] = useState<string | null>(null);
  const [existingNERModels, setExistingNERModels] = useState<SelectModel[]>([]);
  const [grIdentifier, setGrIdentifier] = useState<string | null>(null);
  const [grModelId, setGrModelId] = useState<string | null>(null);
  const [createdGR, setCreatedGR] = useState<boolean>(false);

  useEffect(() => {
    setExistingNERModels(models.filter((model) => model.type === 'udt'));
  }, [models]);

  // End state variables & func for LLM guardrail

  const [modelName, setModelName] = useState('');

  // Begin state variables & func for LLM

  const [llmType, setLlmType] = useState<string | null>(null);

  // End state variables & func for LLM

  const router = useRouter();

  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async () => {
    setIsLoading(true);

    const workflowName = modelName;
    const workflowTypeName = 'rag';

    try {
      // Step 1: Create the workflow
      const workflowResponse = await create_workflow({
        name: workflowName,
        typeName: workflowTypeName,
      });
      const workflowId = workflowResponse.data.workflow_id;
      console.log('Workflow created:', workflowId);

      // Step 2: Prepare the models to be added
      const modelIdentifiers = [];
      const components = [];

      // Find and add the semantic search model
      if (ssModelId) {
        modelIdentifiers.push(ssModelId);
        components.push('search');
      } else {
        console.error(`Semantic search model with identifier ${ssIdentifier} not found.`);
        alert(`Semantic search model with identifier ${ssIdentifier} not found.`);
      }

      // Find and add the NER model if it exists
      if (grModelId) {
        modelIdentifiers.push(grModelId);
        components.push('nlp');
      } else {
        console.error(`NER model with identifier ${grIdentifier} not found.`);
        // alert(`NER model with identifier ${grIdentifier} not found.`)
      }

      // Step 3: Add the models to the workflow
      if (modelIdentifiers.length > 0) {
        const addModelsResponse = await add_models_to_workflow({
          workflowId,
          modelIdentifiers,
          components,
        });
        console.log('Models added to workflow:', addModelsResponse);
      } else {
        console.error('No models to add to the workflow');
        alert('No models to add to the workflow');
      }

      // Step 4: Set the generation AI provider based on the selected LLM type
      let provider = '';
      switch (llmType) {
        case 'OpenAI':
          provider = 'openai';
          break;
        case 'On-prem':
          provider = 'on-prem';
          break;
        case 'Self-host':
          provider = 'self-host';
          break;
        default:
        // handle
      }

      if (provider) {
        const setProviderResponse = await set_gen_ai_provider({
          workflowId,
          provider,
        });
        console.log('Generation AI provider set:', setProviderResponse);
      } else {
        console.error('Invalid LLM type selected');
        alert('Invalid LLM type selected');
      }

      // Go back home page
      router.push('/');
    } catch (error) {
      console.error('Error during workflow creation or model addition:', error);
      alert('Error during workflow creation or model addition:' + error);
      setIsLoading(false);
    }
  };
  //creting dropDownList for choosing model....
  const modelDropDownList = models.map((model) => {
    return {
      id: model.user_id,
      name: model.username + '/' + model.model_name,
    };
  });

  const grDropDownList = existingNERModels.map((model) => {
    return {
      id: model.user_id,
      name: model.username + '/' + model.model_name,
    };
  });

  const handleSSIdentifier = (ssID: string) => {
    setSsIdentifier(ssID);
    const ssModel = existingSSmodels.find(
      (model) => `${model.username}/${model.model_name}` === ssID
    );
    if (ssModel) {
      setSsModelId(ssModel.model_id);
    }
  };

  const handleGrIdentifier = (grID: string) => {
    setGrIdentifier(grID);
    const grModel = existingNERModels.find(
      (model) => `${model.username}/${model.model_name}` === grID
    );
    if (grModel) {
      setGrModelId(grModel.model_id);
    }
  };

  const [warningMessage, setWarningMessage] = useState('');

  const steps = [
    {
      title: 'App Name',
      content: (
        <div>
          <span className="block text-lg font-semibold">App Name</span>
          <TextField
            className="text-md w-full"
            value={modelName}
            onChange={(e) => {
              const name = e.target.value;
              const regexPattern = /^[\w-]+$/;
              let warningMessage = '';

              // Check if the name contains spaces
              if (name.includes(' ')) {
                warningMessage = 'The app name cannot contain spaces. Please remove the spaces.';
              }
              // Check if the name contains periods
              else if (name.includes('.')) {
                warningMessage =
                  "The app name cannot contain periods ('.'). Please remove the periods.";
              }
              // Check if the name contains invalid characters (doesn't match the regex pattern)
              else if (!regexPattern.test(name)) {
                warningMessage =
                  'The app name can only contain letters, numbers, underscores, and hyphens. Please modify the name.';
              }
              // Check if the name is already in use
              else if (workflowNames.includes(name)) {
                warningMessage =
                  'An app with the same name already exists. Please choose a different name.';
              }

              // Set the warning message or clear it if the name is valid
              setWarningMessage(warningMessage);
              setModelName(name);
            }}
            placeholder="Enter app name"
            style={{ marginTop: '10px' }}
          />
          {warningMessage && (
            <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>
          )}
        </div>
      ),
    },
    {
      title: 'Retrieval App',
      content: (
        <div>
          <span className="block text-lg font-semibold">Retrieval App</span>
          {!createdSS && (
            <>
              <CardDescription>Use an existing retrieval app?</CardDescription>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  gap: '10px',
                  marginTop: '10px',
                }}
              >
                <Button
                  variant={ifUseExistingSS === 'Yes' ? 'contained' : 'outlined'}
                  onClick={() => {
                    setUseExistingSS('Yes');
                    setCreatedSS(false);
                  }}
                >
                  Yes
                </Button>
                <Button
                  variant={ifUseExistingSS === 'No' ? 'contained' : 'outlined'}
                  onClick={() => {
                    setUseExistingSS('No');
                    setCreatedSS(false);
                  }}
                >
                  No, create a new one
                </Button>
              </div>
            </>
          )}

          {ifUseExistingSS === 'Yes' && (
            <div className="mb-4 mt-2">
              <CardDescription>Choose from existing semantic search model(s)</CardDescription>
              <div className="mt-2">
                <DropdownMenu
                  title=" Please choose a model  "
                  handleSelectedTeam={handleSSIdentifier}
                  teams={modelDropDownList}
                />
              </div>
            </div>
          )}

          {ifUseExistingSS === 'No' && (
            <>
              {createdSS ? (
                <div>Semantic search model created.</div>
              ) : (
                <div>
                  <SemanticSearchQuestions
                    workflowNames={workflowNames}
                    onCreateModel={(modelID) => {
                      setSsModelId(modelID);
                      setCreatedSS(true);
                    }}
                    stayOnPage={true}
                    appName={`${modelName}-Retrieval`}
                  />
                </div>
              )}
            </>
          )}
        </div>
      ),
    },
    {
      title: 'LLM Guardrail',
      content: (
        <div>
          <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
            LLM Guardrail
          </span>
          {!createdGR && (
            <>
              <CardDescription>Would you like to add LLM guardrail?</CardDescription>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  gap: '10px',
                  marginTop: '10px',
                }}
              >
                <Button
                  variant={ifUseLGR === 'Yes' ? 'contained' : 'outlined'}
                  onClick={() => {
                    setIfUseLGR('Yes');
                    setCreatedGR(false);
                  }}
                >
                  Yes
                </Button>
                <Button
                  variant={ifUseLGR === 'No' ? 'contained' : 'outlined'}
                  onClick={() => {
                    setGrIdentifier(null);
                    setIfUseLGR('No');
                    setCreatedGR(false);
                  }}
                >
                  No
                </Button>
              </div>

              {ifUseLGR === 'Yes' && (
                <>
                  <div style={{ marginTop: '20px' }}>
                    <CardDescription>Use an existing NER model for LLM guardrail?</CardDescription>
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'row',
                        gap: '10px',
                        marginTop: '10px',
                      }}
                    >
                      <Button
                        variant={ifUseExistingLGR === 'Yes' ? 'contained' : 'outlined'}
                        onClick={() => {
                          setIfUseExistingLGR('Yes');
                          setCreatedGR(false);
                        }}
                      >
                        Yes
                      </Button>
                      <Button
                        variant={ifUseExistingLGR === 'No' ? 'contained' : 'outlined'}
                        onClick={() => {
                          setIfUseExistingLGR('No');
                          setCreatedGR(false);
                        }}
                      >
                        No
                      </Button>
                    </div>
                  </div>

                  {ifUseExistingLGR === 'Yes' && (
                    <div style={{ marginTop: '20px' }}>
                      <div className="mb-4 mt-2">
                        <CardDescription>Choose from existing NLP App(s)</CardDescription>
                        <div className="mt-2">
                          <DropdownMenu
                            title=" Please choose a model  "
                            handleSelectedTeam={handleGrIdentifier}
                            teams={grDropDownList}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {ifUseExistingLGR === 'No' && (
                    <>
                      {createdGR ? (
                        <div>Guardrail model created.</div>
                      ) : (
                        <div>
                          <NERQuestions
                            workflowNames={workflowNames}
                            modelGoal="Model to detect sensitive PII"
                            onCreateModel={(modelID) => {
                              setGrModelId(modelID);
                              setCreatedGR(true);
                            }}
                            stayOnPage={true}
                            appName={`${modelName}-NER`}
                          />
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </>
          )}
        </div>
      ),
    },
    {
      title: 'Chat',
      content: (
        <div>
          <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
            Chat
          </span>
          <div>
            <CardDescription>Choose an LLM option</CardDescription>
            <div
              style={{
                display: 'flex',
                flexDirection: 'row',
                gap: '10px',
                marginTop: '10px',
              }}
            >
              <Button
                variant={llmType === 'OpenAI' ? 'contained' : 'outlined'}
                onClick={() => setLlmType('OpenAI')}
              >
                OpenAI
              </Button>
              <Button
                variant={llmType === 'On-Prem' ? 'contained' : 'outlined'}
                onClick={() => setLlmType('On-prem')}
              >
                On-prem
              </Button>
              <Button
                variant={llmType === 'Self-host' ? 'contained' : 'outlined'}
                onClick={() => setLlmType('Self-host')}
              >
                Self-host
              </Button>
            </div>
          </div>
        </div>
      ),
    },
  ];

  // This is for displaying message in case user missed requirements
  const missingRequirements = [];

  if (!modelName) {
    missingRequirements.push('App Name is not specified (Step 1)');
  }

  if (!ssModelId) {
    missingRequirements.push('Retrieval app is not specified (Step 2)');
  }

  if (!(ifUseLGR === 'No' || grModelId)) {
    missingRequirements.push('LLM Guardrail is not specified (Step 3)');
  }

  if (!llmType) {
    missingRequirements.push('LLM Type is not specified (Step 4)');
  }

  const errorMessage =
    missingRequirements.length > 0 ? (
      <div>
        {`Please go back and specify the following:`}
        <br />
        {missingRequirements.map((requirement, index) => (
          <span key={index}>
            {'• '}
            {requirement}
            <br />
          </span>
        ))}
      </div>
    ) : (
      ''
    );

  return (
    <div>
      {/* Step Navigation */}
      <div className="mb-4">
        {steps.map((step, index) => (
          <Button
            key={index}
            variant={index === currentStep ? 'contained' : 'outlined'}
            onClick={() => setCurrentStep(index)}
            style={{ marginRight: '10px' }}
          >
            {step.title}
          </Button>
        ))}
      </div>

      {/* Step Content */}
      <div>{steps[currentStep].content}</div>

      {/* Step Controls */}
      <div className="flex justify-between">
        <div
          style={{
            marginTop: '50px',
          }}
        >
          {/* Previous Button */}
          {currentStep > 0 ? (
            <Button
              onClick={() => setCurrentStep(currentStep - 1)}
              color="error"
              variant="contained"
            >
              Previous
            </Button>
          ) : (
            <></>
          )}
        </div>
        <div>
          {/* Next Button or Create/Deploy Button */}
          {currentStep < steps.length - 1 ? (
            <Button
              onClick={() => setCurrentStep(currentStep + 1)}
              variant="contained"
              style={{
                marginTop: '50px',
              }}
            >
              Next
            </Button>
          ) : (
            <>
              {ssModelId && (ifUseLGR === 'No' || grModelId) && modelName ? (
                <div>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div>
                        <Button
                          onClick={handleSubmit}
                          variant="contained"
                          style={{ width: '100%' }}
                          disabled={
                            isLoading ||
                            !(ssModelId && (ifUseLGR === 'No' || grModelId) && llmType && modelName)
                          }
                        >
                          {isLoading ? (
                            <div className="flex items-center justify-center">
                              <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-2"></div>
                              <span>Creating...</span>
                            </div>
                          ) : (
                            'Create'
                          )}
                        </Button>
                      </div>
                    </TooltipTrigger>
                    {!(ssModelId && (ifUseLGR === 'No' || grModelId) && llmType && modelName) && (
                      <TooltipContent side="bottom">LLM Type is not specified</TooltipContent>
                    )}
                  </Tooltip>
                </div>
              ) : (
                <div style={{ color: 'red' }}>{errorMessage}</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default RAGQuestions;
