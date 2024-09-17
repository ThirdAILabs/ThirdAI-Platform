import React, { useState, useEffect } from 'react';
import { SelectModel } from '@/lib/db';
import NERQuestions from './nlp-questions/ner-questions';
import SemanticSearchQuestions from './semantic-search-questions';
import { create_workflow, add_models_to_workflow, set_gen_ai_provider } from '@/lib/backend';
import { CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useRouter } from 'next/navigation';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

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

  const [warningMessage, setWarningMessage] = useState('');

  const steps = [
    {
      title: 'App Name',
      content: (
        <div>
          <span className="block text-lg font-semibold">App Name</span>
          <Input
            className="text-md"
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
                style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}
              >
                <Button
                  variant={
                    ifUseExistingSS
                      ? ifUseExistingSS === 'Yes'
                        ? 'secondary'
                        : 'outline'
                      : 'default'
                  }
                  onClick={() => {
                    setUseExistingSS('Yes');
                    setCreatedSS(false);
                  }}
                >
                  Yes
                </Button>
                <Button
                  variant={
                    ifUseExistingSS
                      ? ifUseExistingSS === 'No'
                        ? 'secondary'
                        : 'outline'
                      : 'default'
                  }
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
            <div className="mb-4">
              <CardDescription>Choose from existing semantic search model(s)</CardDescription>
              <select
                id="semanticSearchModels"
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                value={ssIdentifier || ''}
                onChange={(e) => {
                  const ssID = e.target.value;
                  setSsIdentifier(ssID);
                  const ssModel = existingSSmodels.find(
                    (model) => `${model.username}/${model.model_name}` === ssID
                  );
                  if (ssModel) {
                    setSsModelId(ssModel.model_id);
                  }
                }}
              >
                <option value="">-- Please choose a model --</option>
                {existingSSmodels.map((model, index) => (
                  <option key={index} value={`${model.username}/${model.model_name}`}>
                    {`${model.username}/${model.model_name}`}
                  </option>
                ))}
              </select>
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
                style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}
              >
                <Button
                  variant={ifUseLGR ? (ifUseLGR === 'Yes' ? 'secondary' : 'outline') : 'default'}
                  onClick={() => {
                    setIfUseLGR('Yes');
                    setCreatedGR(false);
                  }}
                >
                  Yes
                </Button>
                <Button
                  variant={ifUseLGR ? (ifUseLGR === 'No' ? 'secondary' : 'outline') : 'default'}
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
                        variant={
                          ifUseExistingLGR
                            ? ifUseExistingLGR === 'Yes'
                              ? 'secondary'
                              : 'outline'
                            : 'default'
                        }
                        onClick={() => {
                          setIfUseExistingLGR('Yes');
                          setCreatedGR(false);
                        }}
                      >
                        Yes
                      </Button>
                      <Button
                        variant={
                          ifUseExistingLGR
                            ? ifUseExistingLGR === 'No'
                              ? 'secondary'
                              : 'outline'
                            : 'default'
                        }
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
                      <CardDescription>Choose from existing NLP App(s)</CardDescription>
                      <select
                        id="nerModels"
                        className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                        value={grIdentifier ? grIdentifier : ''}
                        onChange={(e) => {
                          const grID = e.target.value;
                          setGrIdentifier(grID);
                          const grModel = existingNERModels.find(
                            (model) => `${model.username}/${model.model_name}` === grID
                          );
                          if (grModel) {
                            setGrModelId(grModel.model_id);
                          }
                        }}
                      >
                        <option value="">-- Please choose a model --</option>
                        {existingNERModels.map((model) => (
                          <option key={model.id} value={`${model.username}/${model.model_name}`}>
                            {`${model.username}/${model.model_name}`}
                          </option>
                        ))}
                      </select>
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
            <div style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}>
              <Button
                variant={llmType ? (llmType === 'OpenAI' ? 'secondary' : 'outline') : 'default'}
                onClick={() => setLlmType('OpenAI')}
              >
                OpenAI
              </Button>
              <Button
                variant={llmType ? (llmType === 'On-prem' ? 'secondary' : 'outline') : 'default'}
                onClick={() => setLlmType('On-prem')}
              >
                On-prem
              </Button>
              <Button
                variant={llmType ? (llmType === 'Self-host' ? 'secondary' : 'outline') : 'default'}
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
            variant={index === currentStep ? 'secondary' : 'outline'}
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
      <div style={{ marginTop: '50px', display: 'flex', justifyContent: 'space-between' }}>
        {/* Previous Button */}
        {currentStep > 0 ? (
          <Button onClick={() => setCurrentStep(currentStep - 1)}>Previous</Button>
        ) : (
          <div></div>
        )}

        {/* Next Button or Create/Deploy Button */}
        {currentStep < steps.length - 1 ? (
          <Button onClick={() => setCurrentStep(currentStep + 1)}>Next</Button>
        ) : (
          <>
            {ssModelId && (ifUseLGR === 'No' || grModelId) && modelName ? (
              <div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div>
                      <Button
                        onClick={handleSubmit}
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
  );
};

export default RAGQuestions;
