import React, { useState, useEffect } from 'react';
import { TextField, Typography, Box, Tooltip, Button, Alert } from '@mui/material';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, HelpCircle } from 'lucide-react';
import {
  retrainTokenClassifier,
  trainUDTWithCSV,
  getTrainReport,
  getAccessToken,
  evaluateModel,
  EvaluationData,
  validateEvalFile,
} from '@/lib/backend';
import RecentSamples from './samples';
import { TrainingResults } from './MetricsChart';
import type { TrainReportData } from '@/lib/backend';
import axios from 'axios';
import { Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import { ExpandMore } from '@mui/icons-material';

interface ModelUpdateProps {
  username: string;
  modelName: string;
  deploymentUrl: string;
  workflowNames: string[];
  deployStatus: string;
}

const getMetricColor = (value: number) => {
  if (value >= 95) return 'text-green-600 font-semibold';
  if (value >= 85) return 'text-yellow-600 font-semibold';
  return 'text-red-600 font-semibold';
};

const MetricCell = ({ value }: { value: number | string }) => {
  if (typeof value === 'number') {
    const percentage = value * 100;
    return (
      <td className={`px-6 py-4 whitespace-nowrap ${getMetricColor(percentage)}`}>
        {percentage.toFixed(1)}%
      </td>
    );
  }
  return <td className="px-6 py-4 whitespace-nowrap text-gray-500">{value}</td>;
};

// Token highlighting component
const TokenHighlight: React.FC<{
  text: string;
  index: number;
  highlightIndex: number;
  type: 'tp' | 'fp' | 'fn';
}> = ({ text, index, highlightIndex, type }) => {
  const isHighlighted = index === highlightIndex;

  const getHighlightColor = () => {
    if (!isHighlighted) return 'bg-transparent';
    switch (type) {
      case 'tp':
        return 'bg-green-100 border-green-400';
      case 'fp':
        return 'bg-red-100 border-red-400';
      case 'fn':
        return 'bg-yellow-100 border-yellow-400';
      default:
        return 'bg-transparent';
    }
  };

  return (
    <span
      className={`px-1 py-0.5 rounded ${getHighlightColor()} ${isHighlighted ? 'border-2' : ''}`}
    >
      {text}
    </span>
  );
};

// Example display component
const ExamplePair: React.FC<{
  example: {
    source: string;
    target: string;
    predictions: string;
    index: number;
  };
  type: 'tp' | 'fp' | 'fn';
}> = ({ example, type }) => {
  const sourceTokens = example.source.split(' ');
  const targetTokens = example.target.split(' ');
  const predictionTokens = example.predictions.split(' ');

  const getTypeLabel = () => {
    switch (type) {
      case 'tp':
        return 'True Positive';
      case 'fp':
        return 'False Positive';
      case 'fn':
        return 'False Negative';
    }
  };

  const getTypeColor = () => {
    switch (type) {
      case 'tp':
        return 'text-green-700 bg-green-50';
      case 'fp':
        return 'text-red-700 bg-red-50';
      case 'fn':
        return 'text-yellow-700 bg-yellow-50';
    }
  };

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${getTypeColor()}`}>
        {getTypeLabel()}
      </div>

      <div className="space-y-2">
        <div className="space-y-1">
          <div className="text-sm font-medium text-gray-500">Input</div>
          <div className="p-2 bg-gray-50 rounded">
            {sourceTokens.map((token, idx) => (
              <React.Fragment key={idx}>
                <TokenHighlight
                  text={token}
                  index={idx}
                  highlightIndex={example.index}
                  type={type}
                />
                {idx < sourceTokens.length - 1 && ' '}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-sm font-medium text-gray-500">Ground Truth</div>
          <div className="p-2 bg-gray-50 rounded">
            {targetTokens.map((token, idx) => (
              <React.Fragment key={idx}>
                <TokenHighlight
                  text={token}
                  index={idx}
                  highlightIndex={example.index}
                  type={type}
                />
                {idx < targetTokens.length - 1 && ' '}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-sm font-medium text-gray-500">Prediction</div>
          <div className="p-2 bg-gray-50 rounded">
            {predictionTokens.map((token, idx) => (
              <React.Fragment key={idx}>
                <TokenHighlight
                  text={token}
                  index={idx}
                  highlightIndex={example.index}
                  type={type}
                />
                {idx < predictionTokens.length - 1 && ' '}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default function ModelUpdate({
  username,
  modelName,
  deploymentUrl,
  workflowNames,
  deployStatus,
}: ModelUpdateProps) {
  // States for CSV upload
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploadUpdating, setIsUploadUpdating] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [newModelName, setNewModelName] = useState(``);
  const [warningMessage, setWarningMessage] = useState('');

  // States for polling method
  const [isPollingUpdating, setIsPollingUpdating] = useState(false);
  const [pollingError, setPollingError] = useState('');
  const [pollingSuccess, setPollingSuccess] = useState(false);

  // States for training report
  const [trainReport, setTrainReport] = useState<TrainReportData | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(true);
  const [reportError, setReportError] = useState('');

  // New states for button cooldown
  const [uploadButtonDisabled, setUploadButtonDisabled] = useState(false);
  const [pollingButtonDisabled, setPollingButtonDisabled] = useState(false);

  //state for toggling tags list
  const [numTagDisplay, setNumTagDisplay] = useState<number>(5);
  const [tags, setTags] = useState<string[]>([]);

  // Effect to validate model name on each change
  useEffect(() => {
    validateModelName(newModelName);
  }, [newModelName, workflowNames]);

  // Timer effect for upload button cooldown
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (uploadButtonDisabled) {
      timer = setTimeout(() => {
        setUploadButtonDisabled(false);
      }, 3000);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [uploadButtonDisabled]);

  // Timer effect for polling button cooldown
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (pollingButtonDisabled) {
      timer = setTimeout(() => {
        setPollingButtonDisabled(false);
      }, 3000);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [pollingButtonDisabled]);

  // Fetch initial training report
  useEffect(() => {
    const fetchInitialReport = async () => {
      try {
        setIsLoadingReport(true);
        setReportError('');
        const response = await getTrainReport(`${username}/${modelName}`);
        setTrainReport(response.data);
      } catch (error) {
        setReportError(error instanceof Error ? error.message : 'Failed to fetch training report');
      } finally {
        setIsLoadingReport(false);
      }
    };

    fetchInitialReport();
  }, [username, modelName]);

  const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB in bytes

  // Fetch initial training report - Using mock data for now
  useEffect(() => {
    const fetchInitialReport = async () => {
      try {
        setIsLoadingReport(true);
        setReportError('');
        const response = await getTrainReport(`${username}/${modelName}`);
        setTrainReport(response.data); // Extract just the data field
      } catch (error) {
        setReportError(error instanceof Error ? error.message : 'Failed to fetch training report');
      } finally {
        setIsLoadingReport(false);
      }
    };

    fetchInitialReport();
  }, [username, modelName]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      // Check file type
      if (file.type !== 'text/csv') {
        setUploadError('Please upload a CSV file');
        setSelectedFile(null);
        return;
      }

      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        setUploadError('File size must be less than 500MB');
        setSelectedFile(null);
        return;
      }

      setSelectedFile(file);
      setUploadError('');
    }
  };

  const validateModelName = (name: string) => {
    // Check if name exists in workflowNames
    if (workflowNames.includes(name)) {
      setWarningMessage(
        'An app with the same name already exists. Please choose a different name.'
      );
      return false;
    }

    // Check for valid characters (alphanumeric, hyphens, and underscores)
    const isValid = /^[a-zA-Z0-9-_]+$/.test(name);
    const isNotEmpty = name.trim().length > 0;

    if (!isValid && isNotEmpty) {
      setWarningMessage(
        'The app name can only contain letters, numbers, underscores, and hyphens. Please modify the name.'
      );
      return false;
    }

    if (name.includes(' ')) {
      setWarningMessage('The app name cannot contain spaces. Please remove the spaces.');
      return false;
    }

    if (name.includes('.')) {
      setWarningMessage("The app name cannot contain periods ('.'). Please remove the periods.");
      return false;
    }

    setWarningMessage('');
    return isValid && isNotEmpty;
  };

  const handleUploadUpdate = async () => {
    if (!selectedFile) {
      setUploadError('Please select a CSV file first');
      return;
    }
    if (!validateModelName(newModelName)) {
      setUploadError(
        'Please enter a valid model name (alphanumeric characters, hyphens, and underscores only)'
      );
      return;
    }

    setIsUploadUpdating(true);
    setUploadError('');
    setUploadSuccess(false);
    setUploadButtonDisabled(true);

    try {
      const response = await trainUDTWithCSV({
        model_name: newModelName,
        file: selectedFile,
        base_model_identifier: `${username}/${modelName}`,
        test_split: 0.1,
      });

      if (response.status === 'success') {
        setUploadSuccess(true);
      } else {
        throw new Error(response.message || 'Failed to initiate update');
      }
    } catch (error) {
      setUploadError(
        error instanceof Error
          ? error.message
          : 'An error occurred while initiating the model update'
      );
    } finally {
      setIsUploadUpdating(false);
    }
  };

  // New state for custom model name in polling section
  const [pollingModelName, setPollingModelName] = useState(``);
  const [pollingWarningMessage, setPollingWarningMessage] = useState('');

  // Effect to validate polling model name
  useEffect(() => {
    validatePollingModelName(pollingModelName);
  }, [pollingModelName, workflowNames]);

  // Validation for polling model name
  const validatePollingModelName = (name: string) => {
    if (workflowNames.includes(name)) {
      setPollingWarningMessage(
        'An app with the same name already exists. Please choose a different name.'
      );
      return false;
    }
    const isValid = /^[a-zA-Z0-9-_]+$/.test(name);
    const isNotEmpty = name.trim().length > 0;
    if (!isValid && isNotEmpty) {
      setPollingWarningMessage(
        'The app name can only contain letters, numbers, underscores, and hyphens.'
      );
      return false;
    }
    if (name.includes(' ')) {
      setPollingWarningMessage('The app name cannot contain spaces.');
      return false;
    }
    if (name.includes('.')) {
      setPollingWarningMessage("The app name cannot contain periods ('.').");
      return false;
    }
    setPollingWarningMessage('');
    return isValid && isNotEmpty;
  };

  const handlePollingUpdate = async () => {
    if (!validatePollingModelName(pollingModelName)) {
      setPollingError('Please enter a valid model name for the new model.');
      return;
    }

    // Check deploy status before proceeding
    if (deployStatus !== 'complete') {
      setPollingError('Model must be fully deployed before updating with user feedback.');
      return;
    }

    setIsPollingUpdating(true);
    setPollingError('');
    setPollingSuccess(false);
    setPollingButtonDisabled(true);

    try {
      const response = await retrainTokenClassifier({
        model_name: pollingModelName, // Use custom name for new model
        base_model_identifier: `${username}/${modelName}`, // Trigger new model creation
      });

      if (response.status === 'success') {
        setPollingSuccess(true);
      } else {
        throw new Error(response.message || 'Failed to initiate update');
      }
    } catch (error) {
      setPollingError(
        error instanceof Error
          ? error.message
          : 'An error occurred while initiating the model update'
      );
    } finally {
      setIsPollingUpdating(false);
    }
  };

  const handleTagDisplayMore = () => {
    setNumTagDisplay(tags.length);
  };

  const handleTagDisplayLess = () => {
    setNumTagDisplay(5);
  };

  const getLabels = async (): Promise<string[]> => {
    axios.defaults.headers.common.Authorization = `Bearer ${getAccessToken()}`;
    try {
      const response = await axios.get(`${deploymentUrl}/get_labels`);
      return response.data.data;
    } catch (error) {
      console.error('Error fetching labels:', error);
      alert('Error fetching labels:' + error);
      throw new Error('Failed to fetch labels');
    }
  };

  const [evalFile, setEvalFile] = useState<File | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evalError, setEvalError] = useState('');
  const [evalResults, setEvalResults] = useState<EvaluationData | null>(null);

  // Add this handler function:
  const handleEvalFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.type !== 'text/csv') {
        setEvalError('Please upload a CSV file');
        setEvalFile(null);
        return;
      }

      if (file.size > MAX_FILE_SIZE) {
        setEvalError('File size must be less than 500MB');
        setEvalFile(null);
        return;
      }

      setEvalFile(file);
      setEvalError('');
    }
  };

  const handleEvaluate = async () => {
    if (!evalFile) {
      setEvalError('Please select a CSV file first');
      return;
    }

    // Validate file before processing
    const validation = validateEvalFile(evalFile);
    if (!validation.isValid) {
      setEvalError(validation.error!);
      return;
    }

    setIsEvaluating(true);
    setEvalError('');
    setEvalResults(null);

    try {
      const results = await evaluateModel(deploymentUrl, evalFile);
      setEvalResults(results);
    } catch (error) {
      setEvalError(error instanceof Error ? error.message : 'Failed to evaluate model');
    } finally {
      setIsEvaluating(false);
    }
  };

  useEffect(() => {
    async function getTags() {
      try {
        const labels = await getLabels();
        const filteredLabels = labels.filter((label) => label !== 'O');
        console.log('Filtered labels: ', filteredLabels);
        setTags(filteredLabels);
        // setTags(["phone number", "name", "Anand", "Gautam", "pratik", "tharun", "sid", "yash", "Alice", "Charlie", "Diana", "Eve", "Frank", "Grace", "Ivy", "Jack", "Katie", "Liam", "Mia", "Noah", "Olivia", "Paul", "Quinn", "Ray", "Sophia", "Tom", "Ursula", "Victor", "Wendy", "Xavier", "Yara", "Zach", "Aria", "Bea", "Caleb", "Duke", "Ella", "Finn"])
      } catch (err) {
        if (err instanceof Error) {
          console.log(err.message);
        } else {
          console.log('An unknown error occurred');
        }
      }
    }
    getTags();
  }, []);

  const [selectedLabel, setSelectedLabel] = useState<string>('');
  const [selectedType, setSelectedType] = useState<'tp' | 'fp' | 'fn'>('tp');

  useEffect(() => {
    if (evalResults?.metrics) {
      const labels = Object.keys(evalResults.metrics);
      if (labels.length > 0 && !labels.includes(selectedLabel)) {
        setSelectedLabel(labels[0]);
      }
    }
  }, [evalResults]);

  return (
    <div className="space-y-6 px-1">
      {/* Training Report Section */}

      {isLoadingReport ? (
        <Card>
          <CardContent>
            <div className="text-center py-8">Loading training report...</div>
          </CardContent>
        </Card>
      ) : reportError ? (
        <></>
      ) : (
        trainReport && <TrainingResults report={trainReport} />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Evaluate Model Performance</CardTitle>
          <CardDescription>
            Upload a test CSV file to evaluate the model's performance. The CSV should follow the
            same format as training data:
            <br />
            <br />
            {`• Two columns: 'source' and 'target'`}
            <br />
            {`• Source column: Contains full text`}
            <br />
            {`• Target column: Space-separated labels matching each word/token from source`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div
              className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-blue-500 transition-colors"
              onClick={() => document.getElementById('eval-file-input')?.click()}
            >
              <input
                type="file"
                id="eval-file-input"
                className="hidden"
                accept=".csv"
                onChange={handleEvalFileInput}
              />
              <Upload className="mx-auto mb-2 text-gray-400" size={24} />
              {evalFile ? (
                <p className="text-green-600">Selected: {evalFile.name}</p>
              ) : (
                <p className="text-gray-600">Click to select a test CSV file</p>
              )}
            </div>

            {evalError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {evalError}
              </Alert>
            )}

            <Button
              onClick={handleEvaluate}
              disabled={isEvaluating || !evalFile}
              variant="contained"
              color="primary"
              fullWidth
            >
              {isEvaluating ? 'Evaluating...' : 'Evaluate Model'}
            </Button>

            {evalResults && (
              <div className="space-y-8">
                {/* Metrics Dashboard */}
                <div className="mt-6">
                  <Typography variant="h6" className="mb-4">
                    Performance Dashboard
                  </Typography>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Label
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Precision
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Recall
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            F1 Score
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {Object.entries(evalResults.metrics).map(([label, metrics]) => (
                          <tr key={label} className="hover:bg-gray-50 transition-colors">
                            <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900">
                              {label}
                            </td>
                            <MetricCell value={metrics.precision} />
                            <MetricCell value={metrics.recall} />
                            <MetricCell value={metrics.fmeasure} />
                          </tr>
                        ))}
                        {/* Average row */}
                        <tr className="bg-gray-50 font-medium">
                          <td className="px-6 py-4 whitespace-nowrap">Average</td>
                          {['precision', 'recall', 'fmeasure'].map((metric) => {
                            const values = Object.values(evalResults.metrics)
                              .map((m) => m[metric as keyof typeof m])
                              .filter((value): value is number => typeof value === 'number');
                            const average = values.length
                              ? values.reduce((a, b) => a + b, 0) / values.length
                              : 0;
                            return <MetricCell key={metric} value={average} />;
                          })}
                        </tr>
                      </tbody>
                    </table>

                    {/* Legend */}
                    <div className="mt-4 flex gap-6 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-3 h-3 bg-green-600 rounded-full" />
                        <span>Excellent (≥95%)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-3 h-3 bg-yellow-600 rounded-full" />
                        <span>Good (85-94%)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-3 h-3 bg-red-600 rounded-full" />
                        <span>Needs Improvement (Below 85%)</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Examples Section */}
                <div className="mt-8">
                  <Typography variant="h6" className="mb-4">
                    Example Cases
                  </Typography>

                  {/* Label Selection */}
                  <div className="space-y-2 mt-4">
                    <div className="text-sm font-medium text-gray-500">Select Label</div>
                    <div className="flex flex-wrap gap-2">
                      {Object.keys(evalResults.metrics).map((label) => (
                        <button
                          key={label}
                          onClick={() => setSelectedLabel(label)}
                          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors
                      ${
                        selectedLabel === label
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Prediction Type Selection */}
                  <div className="space-y-2 mt-4">
                    <div className="text-sm font-medium text-gray-500">Select Prediction Type</div>
                    <div className="flex flex-wrap gap-2">
                      {[
                        {
                          id: 'tp',
                          label: 'True Positives',
                          color: 'bg-green-100 hover:bg-green-200',
                        },
                        {
                          id: 'fp',
                          label: 'False Positives',
                          color: 'bg-red-100 hover:bg-red-200',
                        },
                        {
                          id: 'fn',
                          label: 'False Negatives',
                          color: 'bg-yellow-100 hover:bg-yellow-200',
                        },
                      ].map(({ id, label, color }) => (
                        <button
                          key={id}
                          onClick={() => setSelectedType(id as 'tp' | 'fp' | 'fn')}
                          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors
                      ${selectedType === id ? color : 'bg-gray-100 hover:bg-gray-200'}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Examples Display */}
                  {selectedLabel && (
                    <div className="space-y-4 mt-6">
                      {(selectedType === 'tp'
                        ? evalResults.examples.true_positives[selectedLabel] || []
                        : selectedType === 'fp'
                          ? evalResults.examples.false_positives[selectedLabel] || []
                          : evalResults.examples.false_negatives[selectedLabel] || []
                      ).map((example, idx) => (
                        <ExamplePair key={idx} example={example} type={selectedType} />
                      ))}
                      {(selectedType === 'tp'
                        ? !evalResults.examples.true_positives[selectedLabel]?.length
                        : selectedType === 'fp'
                          ? !evalResults.examples.false_positives[selectedLabel]?.length
                          : !evalResults.examples.false_negatives[selectedLabel]?.length) && (
                        <div className="text-center py-8 text-gray-500">
                          No examples found for this combination
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* CSV Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle>Update Model with your own data</CardTitle>
          <CardDescription>
            {`Upload a CSV file with token-level annotations. Your CSV file should follow these requirements:`}
            <br />
            <br />
            {`• Two columns: 'source' and 'target'`}
            <br />
            {`• Source column: Contains full text`}
            <br />
            {`• Target column: Space-separated labels matching each word/token from source`}
            <br />
            {`• IMPORTANT: Number of tokens in source (split by space) MUST match number of labels in target`}
            <br />
            <br />
            {`Example (6 tokens each):`}
            <br />
            {`Source: "The borrower name is John Smith"`}
            <br />
            {`Target: "O O O O NAME NAME"`}
            <br />
            <br />
            <div className="flex flex-wrap gap-2">
              <span className="">Tags Used for Training: </span>
              <div className="w-fit max-w-[600px]">
                {/* Tags Box */}
                <div className="p-1 border-2 border-slate-300 rounded-lg flex flex-wrap">
                  {tags.map(
                    (tag, index) =>
                      index < numTagDisplay && (
                        <div className="rounded-lg p-2 m-2 bg-slate-100" key={`${index}-${tag}`}>
                          {tag}
                        </div>
                      )
                  )}
                  {tags.length > 5 && (
                    <Button
                      color="inherit"
                      variant="outlined"
                      size="medium"
                      onClick={numTagDisplay === 5 ? handleTagDisplayMore : handleTagDisplayLess}
                    >
                      {numTagDisplay === 5 ? 'Expand ▼' : 'Collapse ▲'}
                    </Button>
                  )}
                </div>
              </div>
            </div>

            <br />
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Typography variant="h6" component="h3" sx={{ mr: 1 }}>
                  Name Your Updated Model
                </Typography>
                <Tooltip title="Use alphanumeric characters, hyphens, and underscores only. This will be the identifier for your updated model.">
                  <HelpCircle size={20} />
                </Tooltip>
              </Box>
              <TextField
                fullWidth
                id="model-name"
                label="New Model Name"
                variant="outlined"
                value={newModelName}
                onChange={(e) => setNewModelName(e.target.value)}
                placeholder="Enter new model name"
                helperText={warningMessage || 'Example: my-model-v2 or updated_model_123'}
                error={!!warningMessage}
                sx={{ mt: 1 }}
              />
            </Box>
            <div
              className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-blue-500 transition-colors"
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <input
                type="file"
                id="file-input"
                className="hidden"
                accept=".csv"
                onChange={handleFileInput}
              />
              <Upload className="mx-auto mb-2 text-gray-400" size={24} />
              {selectedFile ? (
                <p className="text-green-600">Selected: {selectedFile.name}</p>
              ) : (
                <p className="text-gray-600">Click to select a CSV file</p>
              )}
            </div>

            {uploadError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {uploadError}
              </Alert>
            )}

            {uploadSuccess && (
              <Alert severity="success" sx={{ mb: 2 }}>
                Update process initiated successfully with uploaded CSV.
              </Alert>
            )}

            <Button
              onClick={handleUploadUpdate}
              disabled={isUploadUpdating || !selectedFile || uploadButtonDisabled}
              variant="contained"
              color={uploadSuccess ? 'success' : 'primary'}
              fullWidth
            >
              {isUploadUpdating
                ? 'Initiating Update...'
                : uploadSuccess
                  ? 'Update Initiated!'
                  : 'Update Model with CSV'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Polled Data Section with Recent Samples */}
      <Card>
        <CardHeader>
          <CardTitle>Update Model with Recent User Feedback</CardTitle>
          <CardDescription>View and use recent labeled samples to update the model</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Typography variant="h6" component="h3" sx={{ mr: 1 }}>
                Name Your New Model
              </Typography>
              <Tooltip title="Use alphanumeric characters, hyphens, and underscores only. This will be the identifier for your updated model.">
                <HelpCircle size={20} />
              </Tooltip>
            </Box>
            <TextField
              fullWidth
              id="polling-model-name"
              label="New Model Name"
              variant="outlined"
              value={pollingModelName}
              onChange={(e) => setPollingModelName(e.target.value)}
              placeholder="Enter new model name"
              helperText={pollingWarningMessage || 'Example: my-model-v2 or updated_model_123'}
              error={!!pollingWarningMessage}
              sx={{ mt: 1 }}
            />
          </Box>

          <div className="mb-6">
            <RecentSamples deploymentUrl={deploymentUrl} />
          </div>

          <div className="space-y-4">
            {pollingError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {pollingError}
              </Alert>
            )}

            {pollingSuccess && (
              <Alert severity="success" sx={{ mb: 2 }}>
                Update process initiated successfully with polled data.
              </Alert>
            )}

            <Button
              onClick={handlePollingUpdate}
              disabled={isPollingUpdating || pollingButtonDisabled || deployStatus !== 'complete'}
              variant="contained"
              color={pollingSuccess ? 'success' : 'primary'}
              fullWidth
            >
              {isPollingUpdating
                ? 'Initiating Update...'
                : pollingSuccess
                  ? 'Update Initiated!'
                  : deployStatus !== 'complete'
                    ? "Model Must Be Deployed First (refresh page once it's deployed)"
                    : 'Update Model with User Feedback'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
