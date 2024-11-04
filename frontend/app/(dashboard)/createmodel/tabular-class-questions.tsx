import React, { useState } from 'react';
import Papa from 'papaparse';
import { Button } from '@mui/material';
import { Input } from '@/components/ui/input';
import { CardDescription } from '@/components/ui/card';

interface TabularClassificationQuestionsProps {
  workflowNames: string[];
  onCreateModel?: (modelID: string) => void;
  stayOnPage?: boolean;
  appName?: string;
}

type ColumnType = 'string' | 'number' | 'boolean' | 'date';

interface DetectedColumn {
  name: string;
  type: ColumnType;
}

const detectColumnType = (values: string[]): ColumnType => {
  if (values.every((val) => !isNaN(Number(val)))) return 'number';
  if (values.every((val) => val === 'true' || val === 'false')) return 'boolean';
  if (values.every((val) => !isNaN(Date.parse(val)))) return 'date';
  return 'string';
};

const TabularClassificationQuestions: React.FC<TabularClassificationQuestionsProps> = ({
  workflowNames,
  onCreateModel,
  stayOnPage,
  appName,
}) => {
  const [modelName, setModelName] = useState<string>(appName || '');
  const [warningMessage, setWarningMessage] = useState<string>('');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [columns, setColumns] = useState<DetectedColumn[]>([]);
  const [targetColumn, setTargetColumn] = useState<string | null>(null);

  // Parse the CSV file and detect column names and types
  const handleCsvFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type === 'text/csv') {
      setCsvFile(file);
      setWarningMessage('');

      // Parse the CSV file
      Papa.parse(file, {
        header: true, // Parse the file as a header row
        skipEmptyLines: true,
        complete: (results) => {
          const data = results.data as Record<string, string>[]; // Data is an array of objects
          if (data.length > 0) {
            // Extract the header (column names)
            const header = Object.keys(data[0]);
            // Detect the types based on the first few rows of data
            const detectedColumns: DetectedColumn[] = header.map((col) => {
              const values = data.map((row) => row[col]);
              return { name: col, type: detectColumnType(values) };
            });
            setColumns(detectedColumns); // Set the columns with names and types
            setTargetColumn(null); // Reset target column
          }
        },
        error: (err) => {
          console.error('Error parsing CSV file:', err);
        },
      });
    } else {
      setWarningMessage('Please upload a valid CSV file.');
    }
  };

  // Handle form submission
  const submit = async () => {
    if (!modelName) {
      setWarningMessage('Please give the app a name.');
      return;
    }

    if (!csvFile || columns.length === 0) {
      setWarningMessage('Please upload a CSV file.');
      return;
    }

    if (!targetColumn) {
      setWarningMessage('Please select a target column.');
      return;
    }

    setIsLoading(true);

    // Your form submission logic goes here
    try {
      console.log('Submitting form with:', {
        modelName,
        csvFile,
        targetColumn,
      });

      if (onCreateModel) {
        onCreateModel('model_id_example');
      }

      if (!stayOnPage) {
        // Redirect logic here
      }
    } catch (error) {
      console.error('Error submitting the form:', error);
    } finally {
      setIsLoading(false);
    }
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
        disabled={!!appName && !workflowNames.includes(modelName)}
      />

      {warningMessage && <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>}

      <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
        Upload CSV File
      </span>
      <CardDescription>Upload a CSV file for tabular classification.</CardDescription>

      <div style={{ marginTop: '10px' }}>
        <Input type="file" accept=".csv" onChange={handleCsvFileChange} />
        {csvFile && (
          <span style={{ marginTop: '10px', display: 'block' }}>Selected file: {csvFile.name}</span>
        )}
      </div>

      {columns.length > 0 && (
        <>
          <div style={{ marginTop: '20px' }}>
            <span className="block text-lg font-semibold">Detected Columns</span>
            <ul>
              {columns.map((col) => (
                <li key={col.name}>
                  {col.name}: {col.type}
                </li>
              ))}
            </ul>
          </div>

          <div style={{ marginTop: '20px' }}>
            <span className="block text-lg font-semibold">Select Target Column</span>
            <CardDescription>
              Select the target prediction column from the detected columns.
            </CardDescription>
            <select
              className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
              value={targetColumn || ''}
              onChange={(e) => setTargetColumn(e.target.value)}
            >
              <option value="" disabled>
                Select a target column
              </option>
              {columns.map((col) => (
                <option key={col.name} value={col.name}>
                  {col.name}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      <div className="flex justify-start">
        <Button
          onClick={submit}
          style={{ marginTop: '30px', width: '100%' }}
          disabled={isLoading || !csvFile || !!warningMessage || !targetColumn}
          variant="contained"
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

export default TabularClassificationQuestions;
