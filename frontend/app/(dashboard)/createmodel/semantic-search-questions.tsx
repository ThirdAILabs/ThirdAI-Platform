import React, { useState, useEffect } from 'react';
import { train_ndb } from '@/lib/backend';
import { Workflow } from '@/lib/backend';
import { Button, TextField } from '@mui/material';
import { CardDescription } from '@/components/ui/card';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface SemanticSearchQuestionsProps {
  workflowNames: string[];
  models: Workflow[];
  onCreateModel?: (modelID: string) => void;
  stayOnPage?: boolean;
  appName?: string;
}

enum SourceType {
  S3 = 's3',
  LOCAL = 'local',
  NSF = 'nsf',
  AZURE = 'azure',
  GCP = 'gcp',
}

enum IndexingType {
  Basic = 'basic',
  Advanced = 'advanced',
}

enum ParsingType {
  Basic = 'basic',
  Advanced = 'advanced',
}

const ALLOWED_FILE_TYPES = '.csv,.pdf,.docx';
const ALLOWED_FILE_TYPES_ARRAY = ['csv', 'pdf', 'docx'];

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
  const [indexingType, setIndexingType] = useState<IndexingType>(IndexingType.Basic);
  const [parsingType, setParsingType] = useState<ParsingType>(ParsingType.Basic);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState(false);
  const [fileError, setFileError] = useState<string>('');

  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const validateFileTypes = (files: FileList): boolean => {
    for (let i = 0; i < files.length; i++) {
      const extension = files[i].name.split('.').pop()?.toLowerCase();
      if (!extension || !ALLOWED_FILE_TYPES_ARRAY.includes(extension)) {
        setFileError(
          `Invalid file type: ${files[i].name}. Only CSV, PDF, and DOCX files are allowed.`
        );
        return false;
      }
    }
    setFileError('');
    return true;
  };

  const addSource = (type: SourceType) => {
    setSources((prev) => [...prev, { type, files: [] }]);
    setFileCount((prev) => [...prev, 0]);
  };

  const setSourceValue = (index: number, files: FileList) => {
    if (!validateFileTypes(files)) {
      return;
    }

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

  const setAzureSourceValue = (index: number, url: string) => {
    const newSources = [...sources];
    const file = new File([], url); // Create a dummy File object with the Azure URL as the name
    newSources[index].files = [file];
    setSources(newSources);

    const newFileCount = [...fileCount];
    newFileCount[index] = 1; // Since it's a single Azure URL
    setFileCount(newFileCount);
  };

  const setGCPSourceValue = (index: number, url: string) => {
    const newSources = [...sources];
    const file = new File([], url); // Create a dummy File object with the GCP URL as the name
    newSources[index].files = [file];
    setSources(newSources);

    const newFileCount = [...fileCount];
    newFileCount[index] = 1; // Since it's a single GCP URL
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

    // If user didn't select advanced, it will not add the advanced_search field at all
    const modelOptionsForm = {
      ndb_options: {
        ndb_sub_type: 'v2',
        ...(indexingType === IndexingType.Advanced && { advanced_search: true }),
      },
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
      <span className="block text-lg font-semibold mt-6">Knowledge Base Name</span>
      <TextField
        className="text-md w-full"
        value={modelName}
        onChange={(e) => {
          const name = e.target.value;
          const regexPattern = /^[\w-]+$/;
          let warningMessage = '';

          if (name.includes(' ')) {
            warningMessage = 'The app name cannot contain spaces. Please remove the spaces.';
          } else if (name.includes('.')) {
            warningMessage =
              "The app name cannot contain periods ('.'). Please remove the periods.";
          } else if (!regexPattern.test(name)) {
            warningMessage =
              'The app name can only contain letters, numbers, underscores, and hyphens. Please modify the name.';
          } else if (workflowNames.includes(name)) {
            warningMessage =
              'An app with the same name already exists. Please choose a different name.';
          }

          setWarningMessage(warningMessage);
          setModelName(name);
        }}
        placeholder="Enter app name"
        style={{ marginTop: '10px' }}
        disabled={!!appName && !workflowNames.includes(modelName)}
      />

      {warningMessage && <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>}

      {/* Sources Section */}
      <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
        Sources
      </span>
      <CardDescription>Select files from:</CardDescription>

      {fileError && <div className="text-red-500 mt-2 mb-2">{fileError}</div>}

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
              <div className="w-full">
                <Input
                  type="file"
                  className="text-md w-full hover:cursor-pointer"
                  onChange={(e) => {
                    if (e.target.files) {
                      setSourceValue(index, e.target.files);
                    }
                  }}
                  accept={ALLOWED_FILE_TYPES}
                  multiple
                />
              </div>
            )}
            {type === SourceType.NSF && (
              <TextField
                className="text-md w-full"
                onChange={(e) => setNSFSourceValue(index, e.target.value)}
                placeholder="Enter NSF server file path"
              />
            )}
            {type === SourceType.AZURE && (
              <TextField
                className="text-md w-full"
                onChange={(e) => setAzureSourceValue(index, e.target.value)}
                placeholder="Enter Azure Blob Storage URL"
              />
            )}
            {type === SourceType.GCP && (
              <TextField
                className="text-md w-full"
                onChange={(e) => setGCPSourceValue(index, e.target.value)}
                placeholder="Enter Google Storage gs URL"
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
          Local
        </Button>
        <Button onClick={() => addSource(SourceType.S3)} variant="contained">
          S3 Bucket
        </Button>
        <Button onClick={() => addSource(SourceType.AZURE)} variant="contained">
          Azure Bucket
        </Button>
        <Button onClick={() => addSource(SourceType.GCP)} variant="contained">
          GCP Bucket
        </Button>
      </div>

      {/* Advanced Configuration Dropdown */}
      <div className="mt-6">
        <div
          className="flex items-center gap-2 cursor-pointer"
          onClick={() => setShowAdvancedConfig(!showAdvancedConfig)}
        >
          <span className="block text-lg font-semibold">Advanced Options</span>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`transform transition-transform ${showAdvancedConfig ? 'rotate-90' : ''}`}
          >
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </div>

        {showAdvancedConfig && (
          <div className="mt-4 border rounded-lg p-4">
            {/* Indexing Configuration */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span className="block text-lg font-semibold">Training</span>
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
                    <strong>Basic:</strong> Very Fast , good accuracy <br />
                    <br />
                    <strong>Advanced:</strong> Fast, better accuracy (recommended up-to 1000 pages
                    of documents)
                  </TooltipContent>
                </Tooltip>
              </div>
              <CardDescription>Choose an indexing option</CardDescription>
              <div className="flex flex-row gap-2 mt-2">
                <Button
                  variant={indexingType === IndexingType.Basic ? 'contained' : 'outlined'}
                  onClick={() => setIndexingType(IndexingType.Basic)}
                  style={{ width: '140px' }}
                >
                  Basic
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
            <div className="mt-4">
              <span className="block text-lg font-semibold">Parsing</span>
              <CardDescription>Choose a parsing option</CardDescription>
              <div className="flex flex-row gap-2 mt-2">
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
        )}
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
