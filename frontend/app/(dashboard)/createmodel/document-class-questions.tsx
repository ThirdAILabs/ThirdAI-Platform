import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@mui/material';

enum SourceType {
  LOCAL = 'local',
  S3 = 's3',
  // TODO (anyone): Change this nsf to nfs. There are so many places in frontend which needs to be changed with this.
  NSF = 'nsf',
  // TODO (anyone): Add the corresponding classes for azure and gcp like setAzureSourceValue.. when this use case is needed.
  AZURE = 'azure',
  GCP = 'gcp',
}

interface DocumentClassificationQuestionsProps {
  workflowNames: string[];
}

export default function DocumentClassificationQuestions({
  workflowNames,
}: DocumentClassificationQuestionsProps) {
  const [modelName, setModelName] = useState('');
  const [warningMessage, setWarningMessage] = useState('');
  const [sources, setSources] = useState<{ type: SourceType; value: string | FileList }[]>([]);
  const [folderStructureValid, setFolderStructureValid] = useState(true); // To track validation status
  const [folderValidationMessage, setFolderValidationMessage] = useState('');

  // Add a new source to the list
  const addSource = (type: SourceType) => {
    setSources([...sources, { type, value: '' }]);
  };

  // Set the value for a local file upload
  const setLocalSourceValue = (index: number, files: FileList) => {
    const updatedSources = [...sources];
    updatedSources[index].value = files;
    setSources(updatedSources);
    console.log('files are', files);
    validateFolderStructure(files); // Validate local folder
  };

  // Set the value for an S3 URL
  const setS3SourceValue = (index: number, url: string) => {
    const updatedSources = [...sources];
    updatedSources[index].value = url;
    setSources(updatedSources);
  };

  // Set the value for an NSF path
  const setNSFSourceValue = (index: number, path: string) => {
    const updatedSources = [...sources];
    updatedSources[index].value = path;
    setSources(updatedSources);
  };

  // Function to validate the folder structure for local uploads
  const validateFolderStructure = (files: FileList) => {
    const folderMap: { [key: string]: boolean } = {};
    let rootHasFiles = false;
    let nonPdfFilesFiltered = false; // To track if non-PDF files are filtered

    // Convert FileList to an array
    const allFilesArray = Array.from(files);

    // Filter to get only .pdf files
    const pdfFiles = allFilesArray.filter((file) => file.name.toLowerCase().endsWith('.pdf'));

    // Check if there were any non-PDF files
    if (allFilesArray.length !== pdfFiles.length) {
      nonPdfFilesFiltered = true; // If there are fewer PDF files after filtering, notify the user
    }

    // Iterate through the filtered list of PDF files to check structure
    for (let i = 0; i < pdfFiles.length; i++) {
      const filePath = pdfFiles[i].webkitRelativePath; // Get full path relative to root folder
      const parts = filePath.split('/'); // Split by "/" to get folder structure

      if (parts.length === 2) {
        // This means there's only 1 part after the root folder (i.e., file is directly in the root)
        rootHasFiles = true; // If the root has files, it's invalid
        break;
      }

      if (parts.length === 3) {
        const categoryName = parts[1]; // Second part is the sub-folder (category)
        folderMap[categoryName] = true; // Store sub-folder names as categories
      }
    }

    if (rootHasFiles) {
      setFolderStructureValid(false);
      setFolderValidationMessage(
        'The root folder cannot contain files. It must only contain sub-folders.'
      );
      return;
    }

    if (Object.keys(folderMap).length === 0) {
      setFolderStructureValid(false);
      setFolderValidationMessage('The folder must contain at least one sub-folder with PDF files.');
    } else {
      setFolderStructureValid(true);
      setFolderValidationMessage('');
    }

    // Show message if non-PDF files were filtered out
    if (nonPdfFilesFiltered) {
      setFolderStructureValid(false);
      setFolderValidationMessage('We have filtered non-PDF files.');
    }
  };

  // Function to delete a source
  const deleteSource = (index: number) => {
    const updatedSources = [...sources];
    updatedSources.splice(index, 1);
    setSources(updatedSources);
  };

  return (
    <div>
      <span className="block text-lg font-semibold">App Name</span>
      <Input
        className="text-md"
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
      />

      {warningMessage && <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>}

      <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
        Sources
      </span>
      <div>
        {sources.map(({ type }, index) => (
          <div key={index} style={{ marginTop: '10px' }}>
            {type === SourceType.LOCAL && (
              <Input
                type="file"
                directory="" // Enables folder selection in browsers that support it
                webkitdirectory="true" // Allows selecting entire directories
                onChange={(e) => {
                  if (e.target.files) {
                    setLocalSourceValue(index, e.target.files);
                  }
                }}
              />
            )}
            {type === SourceType.S3 && (
              <Input
                className="text-md"
                onChange={(e) => setS3SourceValue(index, e.target.value)}
                placeholder="Enter S3 bucket URL"
              />
            )}
            {type === SourceType.NSF && (
              <Input
                className="text-md"
                onChange={(e) => setNSFSourceValue(index, e.target.value)}
                placeholder="Enter NSF server path"
              />
            )}
            <Button variant="contained" color="error" onClick={() => deleteSource(index)}>
              Delete
            </Button>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
        <Button onClick={() => addSource(SourceType.LOCAL)} variant="contained">
          Add Local Folder
        </Button>
        <Button onClick={() => addSource(SourceType.S3)} variant="contained">
          Add S3 URL
        </Button>
        <Button onClick={() => addSource(SourceType.NSF)} variant="contained">
          Add NSF Path
        </Button>
      </div>

      {!folderStructureValid && (
        <span style={{ color: 'red', marginTop: '10px' }}>{folderValidationMessage}</span>
      )}

      <div className="flex justify-start">
        <Button
          onClick={() => console.log('Submit Document Classification')}
          style={{ marginTop: '30px', width: '100%' }}
          variant="contained"
        >
          Create
        </Button>
      </div>
    </div>
  );
}
