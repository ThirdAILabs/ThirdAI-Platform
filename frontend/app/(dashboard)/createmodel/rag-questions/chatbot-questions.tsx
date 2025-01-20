import React, { useState, useEffect } from 'react';
import { Workflow } from '@/lib/backend';
import { CardDescription } from '@/components/ui/card';
import { Button, TextField, Stepper, Step, StepLabel, Box } from '@mui/material';
import { useRouter } from 'next/navigation';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import DropdownMenu from '@/components/ui/dropDownMenu';
import { create_enterprise_search_workflow, EnterpriseSearchOptions } from '@/lib/backend';
import SemanticSearchQuestions from '../semantic-search-questions';
import NERQuestions from '../nlp-questions/ner-questions';

interface ChatbotQuestionsProps {
  models: Workflow[];
  workflowNames: string[];
}

enum LlmProvider {
  OpenAI = 'openai',
  OnPrem = 'on-prem',
  SelfHosted = 'self-hosted',
}

const ChatbotQuestions: React.FC<ChatbotQuestionsProps> = ({ models, workflowNames }) => {
  const [currentStep, setCurrentStep] = useState(0);

  // Knowledge base state
  const [ifUseExistingSS, setUseExistingSS] = useState<string | null>(null);
  const [existingSSmodels, setExistingSSmodels] = useState<Workflow[]>([]);
  const [ssIdentifier, setSsIdentifier] = useState<string | null>(null);
  const [ssModelId, setSsModelId] = useState<string | null>(null);
  const [createdSS, setCreatedSS] = useState<boolean>(false);

  // NEW: store the additional attributes (metadata keys) that come from SemanticSearchQuestions
  const [metadataKeys, setMetadataKeys] = useState<Array<{ name: string; description: string }>>(
    []
  );

  useEffect(() => {
    setExistingSSmodels(models.filter((model) => model.type === 'ndb'));
  }, [models]);

  // LLM Guardrail state
  const [ifUseLGR, setIfUseLGR] = useState('');
  const [ifUseExistingLGR, setIfUseExistingLGR] = useState<string | null>(null);
  const [existingNERModels, setExistingNERModels] = useState<Workflow[]>([]);
  const [grIdentifier, setGrIdentifier] = useState<string | null>(null);
  const [grModelId, setGrModelId] = useState<string | null>(null);
  const [createdGR, setCreatedGR] = useState<boolean>(false);

  useEffect(() => {
    setExistingNERModels(
      models.filter((model) => model.type === 'udt' && model.sub_type === 'token')
    );
  }, [models]);

  // Sentiment Analysis state
  const [ifUseNLPClassifier, setIfUseNLPClassifier] = useState<string | null>(null);
  const [nlpClassifierIdentifier, setNlpClassifierIdentifier] = useState<string | null>(null);
  const [nlpClassifierModelId, setNlpClassifierModelId] = useState<string | null>(null);
  const [existingNLPClassifierModels, setExistingNLPClassifierModels] = useState<Workflow[]>([]);

  useEffect(() => {
    setExistingNLPClassifierModels(
      models.filter((model) => model.type === 'udt' && model.sub_type === 'text')
    );
  }, [models]);

  const [modelName, setModelName] = useState('');
  const [llmType, setLlmType] = useState<LlmProvider | null>(null);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [warningMessage, setWarningMessage] = useState('');

  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [isNameValid, setIsNameValid] = useState(false);

  const validateAppName = (name: string): string => {
    if (!name) return 'App name is required.';
    if (name.includes(' ')) return 'The app name cannot contain spaces.';
    if (name.includes('.')) return "The app name cannot contain periods ('.')";
    if (!/^[\w-]+$/.test(name))
      return 'The app name can only contain letters, numbers, underscores, and hyphens.';
    if (workflowNames.includes(name)) return 'An app with the same name already exists.';
    return '';
  };

  const handleNext = () => {
    if (currentStep === 0 && !warningMessage && modelName) {
      if (!completedSteps.includes(0)) {
        setCompletedSteps([...completedSteps, 0]);
      }
      setCurrentStep(1);
    } else if (currentStep === 1 && ssModelId) {
      if (!completedSteps.includes(1)) {
        setCompletedSteps([...completedSteps, 1]);
      }
      setCurrentStep(2);
    }
  };

  const handleSubmit = async () => {
    setIsLoading(true);

    try {
      let options: EnterpriseSearchOptions = {
        retrieval_id: ssModelId || '',
        guardrail_id: grModelId || '',
        nlp_classifier_id: nlpClassifierModelId || '',
        llm_provider: '',
        default_mode: 'chat',
        // IMPORTANT: pass the metadata keys here
        metadata_attributes: metadataKeys.map((attr) => ({
          attribute_name: attr.name,
          description: attr.description,
        })),
      };

      switch (llmType) {
        case LlmProvider.OpenAI:
          options.llm_provider = 'openai';
          break;
        case LlmProvider.OnPrem:
          options.llm_provider = 'on-prem';
          break;
        case LlmProvider.SelfHosted:
          options.llm_provider = 'self-host';
          break;
        default:
          console.error('Invalid LLM type selected');
          alert('Invalid LLM type selected');
          setIsLoading(false);
          return;
      }

      options = Object.fromEntries(
        Object.entries(options).filter(([_, v]) => v !== undefined && v !== '')
      ) as EnterpriseSearchOptions;

      const workflowResponse = await create_enterprise_search_workflow({
        workflow_name: modelName,
        options,
      });
      console.log('Workflow created:', workflowResponse.data.model_id);
      router.push('/');
    } catch (error) {
      console.error('Error during workflow creation:', error);
      alert('Error during workflow creation: ' + error);
      setIsLoading(false);
    }
  };

  const modelDropDownList = existingSSmodels.map((model) => ({
    id: model.model_id,
    name: model.username + '/' + model.model_name,
  }));

  const grDropDownList = existingNERModels.map((model) => ({
    id: model.model_id,
    name: model.username + '/' + model.model_name,
  }));

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

  const steps = [
    {
      title: 'App Name',
      content: (
        <div className="mt-5">
          <TextField
            className="text-md w-full"
            value={modelName}
            onChange={(e) => {
              const name = e.target.value;
              const warning = validateAppName(name);
              setWarningMessage(warning);
              setModelName(name);
              setIsNameValid(!warning);
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
      title: 'Knowledge base',
      content: (
        <div>
          {!createdSS && (
            <>
              <CardDescription>Would you like to create a new Knowledge Base?</CardDescription>
              <div
                style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}
              >
                <Button
                  variant={ifUseExistingSS === 'No' ? 'contained' : 'outlined'}
                  onClick={() => {
                    setUseExistingSS('No');
                    setCreatedSS(false);
                  }}
                >
                  Yes
                </Button>
                <Button
                  variant={ifUseExistingSS === 'Yes' ? 'contained' : 'outlined'}
                  onClick={() => {
                    setUseExistingSS('Yes');
                    setCreatedSS(false);
                  }}
                >
                  No, use an existing one
                </Button>
              </div>
            </>
          )}

          {ifUseExistingSS === 'Yes' && (
            <div className="mb-4 mt-2">
              <CardDescription>Choose from an existing Knowledge Base</CardDescription>
              <div className="mt-2">
                <DropdownMenu
                  title="Choose a Knowledge Base  "
                  handleSelectedTeam={handleSSIdentifier}
                  teams={modelDropDownList}
                />
              </div>
            </div>
          )}

          {ifUseExistingSS === 'No' && (
            <>
              {createdSS ? (
                <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg shadow-sm">
                  <div className="flex items-center justify-center space-x-3">
                    <span className="text-lg font-medium text-blue-800">Knowledge base queued</span>
                  </div>
                  <div className="mt-2 text-sm text-blue-600 text-center">
                    You may continue to the next step while this processes
                  </div>
                </div>
              ) : (
                <div>
                  <SemanticSearchQuestions
                    models={models}
                    workflowNames={workflowNames}
                    onCreateModel={(modelID) => {
                      setSsModelId(modelID);
                      setCreatedSS(true);
                    }}
                    // Pass a callback that will store the user-defined metadata
                    onMetadataAttributesChange={(newAttributes) => setMetadataKeys(newAttributes)}
                    stayOnPage={true}
                    appName={`${modelName}-KB`}
                  />
                </div>
              )}
            </>
          )}
        </div>
      ),
    },
    {
      title: 'LLM',
      content: (
        <div>
          {/* LLM selection */}
          <div>
            <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
              LLM
            </span>
            <div>
              <CardDescription>Choose an LLM for generating answers</CardDescription>
              <div
                style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}
              >
                <Button
                  variant={llmType === LlmProvider.OpenAI ? 'contained' : 'outlined'}
                  onClick={() => setLlmType(LlmProvider.OpenAI)}
                >
                  OpenAI
                </Button>
                <Button
                  variant={llmType === LlmProvider.OnPrem ? 'contained' : 'outlined'}
                  onClick={() => setLlmType(LlmProvider.OnPrem)}
                >
                  On-prem
                </Button>
                <Button
                  variant={llmType === LlmProvider.SelfHosted ? 'contained' : 'outlined'}
                  onClick={() => setLlmType(LlmProvider.SelfHosted)}
                >
                  Self-host
                </Button>
              </div>
            </div>
          </div>

          {/* LLM Guardrail */}
          <div>
            <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
              LLM Guardrail (Optional)
            </span>
            {!createdGR && (
              <>
                <CardDescription>
                  Would you like to redact PII (Personally Identifiable Information) from your
                  references?
                </CardDescription>
                <div
                  style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}
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
                      <CardDescription>
                        Use an existing NER model to reduce PII from your reference?
                      </CardDescription>
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

          {/* Sentiment Analysis */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', marginTop: '20px' }}>
              <span className="block text-lg font-semibold">Sentiment Analysis (Optional)</span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span style={{ marginLeft: '8px', cursor: 'pointer' }}>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="w-5 h-5"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="8" />
                      <line x1="12" y1="12" x2="12" y2="16" />
                    </svg>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="right" style={{ maxWidth: '250px' }}>
                  A sentiment analysis model can determine the emotional tone behind a user&apos;s
                  query, providing insights into their attitude and emotional state.
                </TooltipContent>
              </Tooltip>
            </div>

            <CardDescription>Would you like to detect sentiment of user query?</CardDescription>
            <div style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}>
              <Button
                variant={ifUseNLPClassifier === 'Yes' ? 'contained' : 'outlined'}
                onClick={() => setIfUseNLPClassifier('Yes')}
              >
                Yes
              </Button>
              <Button
                variant={ifUseNLPClassifier === 'No' ? 'contained' : 'outlined'}
                onClick={() => {
                  setNlpClassifierIdentifier(null);
                  setIfUseNLPClassifier('No');
                }}
              >
                No
              </Button>
            </div>

            {ifUseNLPClassifier === 'Yes' && (
              <div style={{ marginTop: '20px' }}>
                <CardDescription>Choose from existing sentiment analysis models</CardDescription>
                <div className="mt-2">
                  <DropdownMenu
                    title="Please choose a model"
                    handleSelectedTeam={(selectedValue: string, modelId?: string) => {
                      setNlpClassifierIdentifier(selectedValue);
                      if (modelId) {
                        setNlpClassifierModelId(modelId);
                      }
                    }}
                    teams={existingNLPClassifierModels.map((model) => ({
                      id: model.model_id,
                      name: model.username + '/' + model.model_name,
                    }))}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      ),
    },
  ];

  const missingRequirements = [];
  if (!modelName) missingRequirements.push('App Name is not specified (Step 1)');
  if (!ssModelId) missingRequirements.push('Retrieval app is not specified (Step 2)');
  if (!llmType) missingRequirements.push('LLM Type is not specified (Step 3)');

  const errorMessage = missingRequirements.length > 0 && (
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
  );

  return (
    <div>
      <div
        className="mb-4"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-start',
          rowGap: '15px',
          columnGap: '15px',
        }}
      >
        <Box sx={{ width: '100%' }}>
          <Stepper activeStep={currentStep}>
            {steps.map((step, index) => {
              const stepProps: { completed?: boolean } = {};
              const labelProps: {
                optional?: React.ReactNode;
              } = {};
              return (
                <Step key={step.title} {...stepProps}>
                  <StepLabel {...labelProps}>{step.title}</StepLabel>
                </Step>
              );
            })}
          </Stepper>
        </Box>
      </div>

      {/* Step Content */}
      <div className="mt-8">{steps[currentStep].content}</div>

      {/* Step Controls */}
      <div style={{ marginTop: '50px', display: 'flex', justifyContent: 'space-between' }}>
        {currentStep > 0 ? (
          <Button onClick={() => setCurrentStep(currentStep - 1)}>Previous</Button>
        ) : (
          <div></div>
        )}

        {currentStep < steps.length - 1 ? (
          <Button onClick={handleNext} disabled={currentStep === 0 && (!modelName || !isNameValid)}>
            Next
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={isLoading || !(ssModelId && modelName && llmType)}
          >
            {isLoading ? 'Creating...' : 'Create'}
          </Button>
        )}
      </div>
    </div>
  );
};

export default ChatbotQuestions;
