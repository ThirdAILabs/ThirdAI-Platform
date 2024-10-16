import React, { useState, useEffect } from 'react';
import { train_ndb } from '@/lib/backend';
import { SelectModel } from '@/lib/db';
import { Button, TextField } from '@mui/material';
import { CardDescription } from '@/components/ui/card';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/input';
import DropdownMenu from '@/components/ui/dropDownMenu';

interface SemanticSearchQuestionsProps {
  workflowNames: string[];
  models: SelectModel[];
  onCreateModel?: (modelID: string) => void;
  stayOnPage?: boolean;
  appName?: string;
}

enum SourceType {
  S3 = 's3',
  LOCAL = 'local',
  NSF = 'nsf',
}

enum LlmProvider {
  OpenAI = 'openai',
  OnPrem = 'on-prem',
  SelfHosted = 'self-hosted',
}

const SemanticSearchQuestions = ({
  workflowNames,
  models,
  onCreateModel,
  stayOnPage,
  appName,
}: SemanticSearchQuestionsProps) => {
  const [modelName, setModelName] = useState(!appName ? '' : appName);
  const [sources, setSources] = useState<Array<{ type: string; files: File[] }>>([]);
  const [fileCount, setFileCount] = useState<number[]>([]);
  const [llmType, setLlmType] = useState<LlmProvider | null>(null);

  const [ifUseExistingSS, setUseExistingSS] = useState<string | null>(null);
  const [existingSSmodels, setExistingSSmodels] = useState<SelectModel[]>([]);
  const [ssIdentifier, setSsIdentifier] = useState<string | null>(null);
  const [ssModelId, setSsModelId] = useState<string | null>(null);
  const [createdSS, setCreatedSS] = useState<boolean>(false);

  useEffect(() => {
    setExistingSSmodels(models.filter((model) => model.type === 'ndb'));
  }, [models]);

  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const addSource = (type: SourceType) => {
    setSources((prev) => [...prev, { type, files: [] }]);
    setFileCount((prev) => [...prev, 0]);
  };

  const setSourceValue = (index: number, files: FileList) => {
    const newSources = [...sources];
    const fileArray = Array.from(files);
    newSources[index].files = fileArray;
    setSources(newSources);

    const newFileCount = [...fileCount];
    newFileCount[index] = fileArray.length;
    setFileCount(newFileCount);
  };

  const setS3SourceValue = (index: number, url: string) => {
    const newSources = [...sources];
    const file = new File([], url); // Create a dummy File object with the S3 URL as the name
    newSources[index].files = [file];
    setSources(newSources);

    const newFileCount = [...fileCount];
    newFileCount[index] = 1; // Since it's a single S3 URL
    setFileCount(newFileCount);
  };

  const setNSFSourceValue = (index: number, path: string) => {
    const newSources = [...sources];
    const file = new File([], path); // Create a dummy File object with the NSF path as the name
    newSources[index].files = [file];
    setSources(newSources);

    const newFileCount = [...fileCount];
    newFileCount[index] = 1; // It's a single path
    setFileCount(newFileCount);
  };

  const deleteSource = (index: number) => {
    const updatedSources = sources.filter((_, i) => i !== index);
    setSources(updatedSources);
    setFileCount((prev) => prev.filter((_, i) => i !== index));
  };

  const makeFileFormData = () => {
    let formData = new FormData();
    const unsupervisedFiles: Array<{ path: string; location: string }> = [];
    let fileCount = 0;

    sources.forEach(({ type, files }) => {
      files.forEach((file) => {
        formData.append('files', file);
        unsupervisedFiles.push({ path: file.name, location: type });
        fileCount++;
      });
    });

    if (fileCount === 0) {
      return null;
    }

    const modelOptionsForm = {
      ndb_options: { ndb_sub_type: 'v2' },
      llm_provider: llmType ? llmType.toLowerCase() : null,
    };
    formData.append('model_options', JSON.stringify(modelOptionsForm));
    formData.append('file_info', JSON.stringify({ unsupervised_files: unsupervisedFiles }));

    return formData;
  };

  const submit = async () => {
    setIsLoading(true);

    try {
      if (!modelName) {
        alert(
          'Please give the app a name. The name cannot have spaces, forward slashes (/) or colons (:).'
        );
        setIsLoading(false);
        return;
      }
      if (modelName.includes(' ') || modelName.includes('/') || modelName.includes(':')) {
        alert('The app name cannot have spaces, forward slashes (/) or colons (:).');
        setIsLoading(false);
        return;
      }

      console.log(`Submitting model '${modelName}'`);

      let modelId;

      if (ifUseExistingSS === 'Yes') {
        if (!ssModelId) {
          alert('Please select an existing retrieval app.');
          setIsLoading(false);
          return;
        }
        modelId = ssModelId;
      } else {
        const formData = makeFileFormData();

        if (!formData) {
          alert('Please upload at least one file before submitting.');
          setIsLoading(false);
          return;
        }

        // Step 1: Create the model
        const modelResponse = await train_ndb({ name: modelName, formData });
        modelId = modelResponse.data.model_id;

        // This is called from RAG
        if (onCreateModel) {
          onCreateModel(modelId);
        }
      }

      if (!stayOnPage) {
        router.push('/');
      }
    } catch (error) {
      console.log(error);
      setIsLoading(false);
    }
  };

  console.log('sources', sources);

  const [warningMessage, setWarningMessage] = useState('');

  useEffect(() => {
    console.log('appname', appName);
    if (appName) {
      if (workflowNames.includes(appName)) {
        setWarningMessage(
          'An App with the same name has been created. Please choose a different name.'
        );
      } else {
        setWarningMessage(''); // Clear the warning if the name is unique
      }
    }
  }, [appName]);

  return (
    <div>
      <span className="block text-lg font-semibold">App Name</span>
      <TextField
        className="text-md w-full"
        value={modelName}
        onChange={(e) => {
          const name = e.target.value;
          const regexPattern = /^[\w-]+$/;
          let warningMessage = '';

          // Check if the name contains spaces or periods
          if (name.includes(' ')) {
            warningMessage = 'The app name cannot contain spaces. Please remove the spaces.';
          } else if (name.includes('.')) {
            warningMessage =
              "The app name cannot contain periods ('.'). Please remove the periods.";
          }
          // Check if the name contains invalid characters (not matching the regex)
          else if (!regexPattern.test(name)) {
            warningMessage =
              'The app name can only contain letters, numbers, underscores, and hyphens. Please modify the name.';
          }
          // Check if the name is already taken
          else if (workflowNames.includes(name)) {
            warningMessage =
              'An app with the same name already exists. Please choose a different name.';
          }

          // Update the warning message or clear it if valid
          setWarningMessage(warningMessage);
          setModelName(name);
        }}
        placeholder="Enter app name"
        style={{ marginTop: '10px' }}
        disabled={!!appName && !workflowNames.includes(modelName)} // Use !! to explicitly convert to boolean
      />

      {warningMessage && <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>}

      {/* Retrieval App Selection */}
      <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
        Retrieval App
      </span>
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
          <CardDescription>Choose from existing retrieval app(s)</CardDescription>
          <div className="mt-2">
            <DropdownMenu
              title=" Please choose a model  "
              handleSelectedTeam={(ssID: string) => {
                setSsIdentifier(ssID);
                const ssModel = existingSSmodels.find(
                  (model) => `${model.username}/${model.model_name}` === ssID
                );
                if (ssModel) {
                  setSsModelId(ssModel.model_id);
                }
              }}
              teams={existingSSmodels.map((model) => ({
                id: model.model_id,
                name: `${model.username}/${model.model_name}`,
              }))}
            />
          </div>
        </div>
      )}

      {ifUseExistingSS === 'No' && (
        <>
          {createdSS ? (
            <div>Retrieval app created.</div>
          ) : (
            <div>
              <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
                Sources
              </span>
              <CardDescription>Select files to search over.</CardDescription>

              {sources.map(({ type }, index) => (
                <div key={index}>
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'row',
                      gap: '20px',
                      justifyContent: 'space-between',
                      marginTop: '10px',
                    }}
                  >
                    {type === SourceType.S3 && (
                      <TextField
                        className="text-md w-full"
                        onChange={(e) => setS3SourceValue(index, e.target.value)}
                        placeholder="http://s3.amazonaws.com/bucketname/"
                      />
                    )}
                    {type === SourceType.LOCAL && (
                      <div>
                        <Input
                          type="file"
                          onChange={(e) => {
                            if (e.target.files) {
                              setSourceValue(index, e.target.files);
                            }
                          }}
                          multiple
                        />
                      </div>
                    )}
                    {type === SourceType.NSF && ( // New input for NSF server path
                      <TextField
                        className="text-md w-full"
                        onChange={(e) => setNSFSourceValue(index, e.target.value)}
                        placeholder="Enter NSF server file path"
                      />
                    )}
                    <Button variant="contained" color="error" onClick={() => deleteSource(index)}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))}

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                <Button onClick={() => addSource(SourceType.LOCAL)} variant="contained">
                  Add Local File
                </Button>
                <Button onClick={() => addSource(SourceType.S3)} variant="contained">
                  Add S3 File
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* LLM Selection */}
      <div>
        <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
          Summarizer (Optional)
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
              onClick={() => setLlmType(llmType === LlmProvider.OpenAI ? null : LlmProvider.OpenAI)}
            >
              OpenAI
            </Button>
            <Button
              variant={llmType === LlmProvider.OnPrem ? 'contained' : 'outlined'}
              onClick={() => setLlmType(llmType === LlmProvider.OnPrem ? null : LlmProvider.OnPrem)}
            >
              On-prem
            </Button>
            <Button
              variant={llmType === LlmProvider.SelfHosted ? 'contained' : 'outlined'}
              onClick={() =>
                setLlmType(llmType === LlmProvider.SelfHosted ? null : LlmProvider.SelfHosted)
              }
            >
              Self-host
            </Button>
          </div>
        </div>
      </div>

      <div className="flex justify-start">
        <Button
          onClick={submit}
          variant="contained"
          style={{ marginTop: '30px', width: '100%' }}
          disabled={isLoading}
        >
          {isLoading ? (
            <div className="flex items-center">
              <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-2"></div>
              <span>Creating...</span>
            </div>
          ) : (
            'Create'
          )}
        </Button>
      </div>
    </div>
  );
};

export default SemanticSearchQuestions;
