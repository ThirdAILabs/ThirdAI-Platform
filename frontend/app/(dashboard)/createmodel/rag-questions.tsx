import React, { useState, useEffect } from 'react';
import { Workflow } from '@/lib/backend';
import NERQuestions from './nlp-questions/ner-questions';
import SemanticSearchQuestions from './semantic-search-questions';
import { CardDescription } from '@/components/ui/card';
import { Button, TextField } from '@mui/material';
import { useRouter } from 'next/navigation';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import DropdownMenu from '@/components/ui/dropDownMenu';
import { create_enterprise_search_workflow, EnterpriseSearchOptions } from '@/lib/backend';

interface RAGQuestionsProps {
  models: Workflow[];
  workflowNames: string[];
  isChatbot: boolean;
}

enum LlmProvider {
  OpenAI = 'openai',
  OnPrem = 'on-prem',
  SelfHosted = 'self-hosted',
}

enum IndexingType {
  Basic = 'basic',
  Better = 'better',
  Advanced = 'advanced',
}

enum ParsingType {
  Basic = 'basic',
  Advanced = 'advanced',
}

const RAGQuestions = ({ models, workflowNames, isChatbot }: RAGQuestionsProps) => {
  const [currentStep, setCurrentStep] = useState(0);

  // Begin state variables & func for source
  const [ifUseExistingSS, setUseExistingSS] = useState<string | null>(null);
  const [existingSSmodels, setExistingSSmodels] = useState<Workflow[]>([]);
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
  const [existingNERModels, setExistingNERModels] = useState<Workflow[]>([]);
  const [grIdentifier, setGrIdentifier] = useState<string | null>(null);
  const [grModelId, setGrModelId] = useState<string | null>(null);
  const [createdGR, setCreatedGR] = useState<boolean>(false);

  useEffect(() => {
    setExistingNERModels(
      models.filter((model) => model.type === 'udt' && model.sub_type === 'token')
    );
  }, [models]);

  // NLP Classifier state variables
  const [ifUseNLPClassifier, setIfUseNLPClassifier] = useState<string | null>(null);
  const [nlpClassifierIdentifier, setNlpClassifierIdentifier] = useState<string | null>(null);
  const [nlpClassifierModelId, setNlpClassifierModelId] = useState<string | null>(null);
  const [existingNLPClassifierModels, setExistingNLPClassifierModels] = useState<Workflow[]>([]);

  useEffect(() => {
    setExistingNLPClassifierModels(
      models.filter((model) => model.type === 'udt' && model.sub_type === 'text')
    );
  }, [models]);

  // End state variables & func for LLM guardrail

  const [modelName, setModelName] = useState('');

  // Begin state variables & func for LLM

  const [llmType, setLlmType] = useState<LlmProvider | null>(null);

  // End state variables & func for LLM


  // New state variables for Advanced Configuration
  const [indexingType, setIndexingType] = useState<IndexingType>(IndexingType.Basic);
  const [parsingType, setParsingType] = useState<ParsingType>(ParsingType.Basic);

  const router = useRouter();

  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async () => {
    setIsLoading(true);

    const workflowName = modelName;

    try {
      // Prepare options
      let options: EnterpriseSearchOptions = {
        retrieval_id: ssModelId || '',
        guardrail_id: grModelId || '',
        nlp_classifier_id: nlpClassifierModelId || '',
        llm_provider: '',
        default_mode: isChatbot ? 'chat' : 'search',
        // indexing_type: indexingType,
        // parsing_type: parsingType,
      };

      // Set llm_provider based on llmType
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
          if (isChatbot) {
            console.error('Invalid LLM type selected');
            alert('Invalid LLM type selected');
            setIsLoading(false);
            return;
          } else {
            // LLM is not required for enterprise search
            break;
          }
      }

      // Clean up options by removing undefined or empty values
      options = Object.fromEntries(
        Object.entries(options).filter(([_, v]) => v !== undefined && v !== '')
      ) as EnterpriseSearchOptions;

      // Call create_workflow
      const workflowResponse = await create_enterprise_search_workflow({
        workflow_name: workflowName,
        options,
      });
      const workflowId = workflowResponse.data.model_id;
      console.log('Workflow created:', workflowId);

      // Go back home page
      router.push('/');
    } catch (error) {
      console.error('Error during workflow creation:', error);
      alert('Error during workflow creation: ' + error);
      setIsLoading(false);
    }
  };
  // Creating drop-down list for choosing model....
  const modelDropDownList = existingSSmodels.map((model) => {
    return {
      id: model.model_id,
      name: model.username + '/' + model.model_name,
    };
  });

  const grDropDownList = existingNERModels.map((model) => {
    return {
      id: model.model_id,
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
                    models={models}
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
      title: 'LLM',
      content: (
        <div>
          {/* LLM selection */}
          <div>
            <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
              LLM
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

          {/* LLM Guardrail (Optional) */}
          <div>
            <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
              LLM Guardrail (Optional)
            </span>
            {!createdGR && (
              <>
                <CardDescription>
                  Would you like to reduce PII (Personally identifiable information) from your
                  reference?
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

          {/* Sentiment Analysis (Optional) */}
          {isChatbot && (
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
              <div
                style={{ display: 'flex', flexDirection: 'row', gap: '10px', marginTop: '10px' }}
              >
                <Button
                  variant={ifUseNLPClassifier === 'Yes' ? 'contained' : 'outlined'}
                  color={ifUseNLPClassifier === 'Yes' ? 'secondary' : 'primary'}
                  onClick={() => setIfUseNLPClassifier('Yes')}
                >
                  Yes
                </Button>
                <Button
                  variant={ifUseNLPClassifier === 'No' ? 'contained' : 'outlined'}
                  color={ifUseNLPClassifier === 'No' ? 'secondary' : 'primary'}
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
                  <select
                    className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                    value={nlpClassifierIdentifier || ''}
                    onChange={(e) => {
                      const classifierID = e.target.value;
                      setNlpClassifierIdentifier(classifierID);
                      const classifierModel = existingNLPClassifierModels.find(
                        (model) => `${model.username}/${model.model_name}` === classifierID
                      );
                      if (classifierModel) {
                        setNlpClassifierModelId(classifierModel.model_id);
                      }
                    }}
                  >
                    <option value="">-- Please choose a model --</option>
                    {existingNLPClassifierModels.map((model) => (
                      <option key={model.model_id} value={`${model.username}/${model.model_name}`}>
                        {`${model.username}/${model.model_name}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Advanced Configuration',
      content: (
        <div>
          <span className="block text-lg font-semibold">Advanced Configuration</span>
          
          {/* Indexing Configuration */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', marginTop: '20px' }}>
              <span className="block text-lg font-semibold">Indexing</span>
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
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="right" style={{ maxWidth: '300px' }}>
                  <strong>Better:</strong> Up to 5K paragraphs. Includes document level and paragraph level keywords.<br/><br/>
                  <strong>Advanced:</strong> Up to 1000 paragraphs. Generates questions for each chunk, upvotes right away, and caches the answers.
                </TooltipContent>
              </Tooltip>
            </div>
            <CardDescription>Choose an indexing option</CardDescription>
            <div
              style={{
                display: 'flex',
                flexDirection: 'row',
                gap: '10px',
                marginTop: '10px',
              }}
            >
              <Button
                variant={indexingType === IndexingType.Basic ? 'contained' : 'outlined'}
                onClick={() => setIndexingType(IndexingType.Basic)}
                style={{ width: '140px' }}
              >
                Basic
              </Button>
              <Button
                variant={indexingType === IndexingType.Better ? 'contained' : 'outlined'}
                onClick={() => setIndexingType(IndexingType.Better)}
                style={{ width: '140px' }}
              >
                Better
              </Button>
              <Button
                variant={indexingType === IndexingType.Advanced ? 'contained' : 'outlined'}
                onClick={() => setIndexingType(IndexingType.Advanced)}
                style={{ width: '140px' }}
              >
                Advanced
              </Button>
            </div>
          </div>
          
          {/* Parsing Configuration */}
          <div>
            <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
              Parsing
            </span>
            <CardDescription>Choose a parsing option</CardDescription>
            <div
              style={{
                display: 'flex',
                flexDirection: 'row',
                gap: '10px',
                marginTop: '10px',
              }}
            >
              <Button
                variant={parsingType === ParsingType.Basic ? 'contained' : 'outlined'}
                onClick={() => setParsingType(ParsingType.Basic)}
                style={{ width: '140px' }}
              >
                Basic
              </Button>
              <Button
                variant={parsingType === ParsingType.Advanced ? 'contained' : 'outlined'}
                onClick={() => setParsingType(ParsingType.Advanced)}
                style={{ width: '140px' }}
              >
                Advanced
              </Button>
            </div>
          </div>
        </div>
      ),
    },
  ];

  // This is for displaying message in case user missed requirements
  const missingRequirements = [];

  if (!modelName) missingRequirements.push('App Name is not specified (Step 1)');
  if (!ssModelId) missingRequirements.push('Retrieval app is not specified (Step 2)');
  if (!llmType && isChatbot) missingRequirements.push('LLM Type is not specified (Step 3)');

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
      {/* Step Navigation */}
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
        {steps.map((step, index) => (
          <Button
            key={index}
            variant={index === currentStep ? 'contained' : 'outlined'}
            onClick={() => setCurrentStep(index)}
            style={{
              marginBottom: '10px',
              width: '140px',
              height: '40px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textTransform: 'none',
              lineHeight: '1.2',
            }}
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
            {ssModelId && modelName && (llmType || !isChatbot) ? (
              <div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div>
                      <Button
                        onClick={handleSubmit}
                        style={{ width: '100%' }}
                        disabled={isLoading || !(ssModelId && modelName && (llmType || !isChatbot))}
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
                  {!(ssModelId && modelName && (llmType || !isChatbot)) && (
                    <TooltipContent side="bottom">Requirements not met</TooltipContent>
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
