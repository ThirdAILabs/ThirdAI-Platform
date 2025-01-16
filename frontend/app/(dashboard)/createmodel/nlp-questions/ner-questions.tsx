// app/NERQuestions.js
import React, { useEffect, useState } from 'react';
import { getUsername, trainTokenClassifier } from '@/lib/backend';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/input';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  TextField,
  IconButton,
  Divider,
} from '@mui/material';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import { CardDescription } from '@/components/ui/card';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import CSVUpload from './ner-questions-upload-file/CSVUpload';
import { Select, MenuItem } from '@mui/material';

const CREATION_METHODS = {
  // PRETRAINED: 'pretrained',
  UPLOAD_DATA: 'upload-data',
  SYNTHETIC: 'synthetic',
};

type LLMProvider = 'openai' | 'self_hosted';

type Example = {
  text: string;
};

type Category = {
  name: string;
  examples: Example[];
  description: string;
};

const predefinedChoices = ['PHONENUMBER', 'SSN', 'CREDITCARDNUMBER', 'LOCATION', 'NAME'];

interface NERQuestionsProps {
  modelGoal: string;
  workflowNames: string[];
  onCreateModel?: (modelId: string) => void;
  stayOnPage?: boolean;
  appName?: string;
}

const NERQuestions = ({
  workflowNames,
  modelGoal,
  onCreateModel,
  stayOnPage,
  appName,
}: NERQuestionsProps) => {
  const [creationMethod, setCreationMethod] = useState<string>('');
  const [modelName, setModelName] = useState(!appName ? '' : appName);
  const [categories, setCategories] = useState<Category[]>([
    { name: '', examples: [{ text: '' }], description: '' },
  ]);
  const [isDataGenerating, setIsDataGenerating] = useState(false);
  const [generatedData, setGeneratedData] = useState([]);
  const [generateDataPrompt, setGenerateDataPrompt] = useState('');

  const router = useRouter();

  const handleCategoryChange = (
    index: number,
    field: keyof Category,
    value: string | Example[]
  ) => {
    const updatedCategories = [...categories];
    if (field === 'examples') {
      updatedCategories[index][field] = value as Example[];
    } else {
      updatedCategories[index][field] = value as string;
    }
    setCategories(updatedCategories);
  };

  const handleExampleChange = (categoryIndex: number, exampleIndex: number, value: string) => {
    const updatedCategories = [...categories];
    updatedCategories[categoryIndex].examples[exampleIndex].text = value;
    setCategories(updatedCategories);
  };

  const handleAddExample = (categoryIndex: number) => {
    const updatedCategories = [...categories];
    updatedCategories[categoryIndex].examples.push({ text: '' });
    setCategories(updatedCategories);
  };

  const handleRemoveExample = (categoryIndex: number, exampleIndex: number) => {
    const updatedCategories = [...categories];
    updatedCategories[categoryIndex].examples.splice(exampleIndex, 1);
    setCategories(updatedCategories);
  };

  const handleAddCategory = () => {
    setCategories([...categories, { name: '', examples: [{ text: '' }], description: '' }]);
  };

  const validateCategories = () => {
    return categories.every((category: Category) => {
      return (
        category.name &&
        category.examples.length > 0 &&
        category.examples.every((ex) => ex.text) &&
        category.description
      );
    });
  };

  const validateTags = () => {
    // ensure that category.name does not contain space
    return categories.every((category: Category) => {
      return !category.name.includes(' ');
    });
  };

  const handleReview = () => {
    if (validateCategories()) {
      if (validateTags()) {
        return true;
      } else {
        alert('Category Name should not have any space.');
        return false;
      }
    } else {
      alert('All fields (Category Name, Example, Description) must be filled for each category.');
      return false;
    }
  };

  const handleAddAndReviewCategory = () => {
    handleAddCategory();
  };

  const handleRemoveCategory = (index: number) => {
    const updatedCategories = categories.filter((_, i) => i !== index);
    setCategories(updatedCategories);
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    console.log('Categories:', categories);
    // Handle form submission logic here
  };

  const generateData = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    for (const category of categories) {
      if (
        category.name === '' ||
        category.examples.length === 0 ||
        category.examples[0].text === '' ||
        category.description === ''
      ) {
        alert('All tokens must have a name, at least one example, and a description.');
        return;
      }
    }

    if (isDataGenerating) {
      return;
    }

    try {
      setIsDataGenerating(true);

      const response = await fetch('/endpoints/generate-data-token-classification', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ categories }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Network response was not ok');
      }

      const result = await response.json();

      console.log('result', result);
      setGeneratedData(result.syntheticDataPairs);
      setGenerateDataPrompt(result.prompts);

      setIsDataGenerating(false);
    } catch (error) {
      console.error('Error generating data:', error);
      alert('Error generating data:' + error);
      setIsDataGenerating(false);
    }
  };

  const renderTaggedSentence = (pair: { sentence: string; nerData: string[] }) => {
    return pair.sentence.split(' ').map((token, idx) => {
      const tag = pair.nerData[idx];
      if (tag === 'O') {
        return (
          <>
            <span key={idx} style={{ padding: '0 4px' }}>
              {token}
            </span>{' '}
          </>
        );
      }
      return (
        <>
          <span
            key={idx}
            style={{
              padding: '0 4px',
              backgroundColor: tag === 'AGE' ? '#ffcccb' : '#ccffcc',
              borderRadius: '4px',
            }}
          >
            {token}{' '}
            <span
              style={{
                fontSize: '0.8em',
                fontWeight: 'bold',
                color: tag === 'AGE' ? '#ff0000' : '#00cc00',
              }}
            >
              {tag}
            </span>
          </span>{' '}
        </>
      );
    });
  };

  const [isLoading, setIsLoading] = useState(false);
  const [llmProvider, setLLMProvider] = useState<LLMProvider>('openai');

  const handleCreateNERModel = async () => {
    if (!modelName) {
      alert('Please enter a model name.');
      return;
    }
    if (warningMessage !== '') {
      return;
    }

    setIsLoading(true);

    try {
      const modelResponse = await trainTokenClassifier(modelName, modelGoal, categories, llmProvider);
      const modelId = modelResponse.data.model_id;

      if (onCreateModel) {
        onCreateModel(modelId);
      }

      console.log('NER model creation successful:', modelResponse);

      if (!stayOnPage) {
        router.push('/');
      }
    } catch (e) {
      console.log(e || 'Failed to create NER model');
    } finally {
      setIsLoading(false);
    }
  };

  const [warningMessage, setWarningMessage] = useState('');

  useEffect(() => {
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

  const renderCreationMethodSelection = () => (
    <Box sx={{ width: '100%', mb: 4 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Choose how you want to create your Text Extraction model
      </Typography>

      <Grid container spacing={2}>
        {/* Pretrained Model Option */}
        {/* <Grid item xs={12} md={4}>
          <Card
            sx={{
              height: '100%',
              cursor: 'pointer',
              border:
                creationMethod === CREATION_METHODS.PRETRAINED
                  ? '2px solid #1976d2'
                  : '1px solid #e0e0e0',
              '&:hover': { borderColor: '#1976d2' },
            }}
            onClick={() => setCreationMethod(CREATION_METHODS.PRETRAINED)}
          >
            <CardContent
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
              }}
            >
              <ModelTrainingIcon sx={{ fontSize: 40, mb: 2, color: 'primary.main' }} />
              <Typography variant="h6" gutterBottom>
                Use Pretrained Model
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Quick start with our pre-trained models for extracting common PII info like Names,
                Addresses, Emails, SSNs etc
              </Typography>
            </CardContent>
          </Card>
        </Grid> */}

        {/* Upload Data Option */}
        <Grid item xs={12} md={4}>
          <Card
            sx={{
              height: '100%',
              cursor: 'pointer',
              border:
                creationMethod === CREATION_METHODS.UPLOAD_DATA
                  ? '2px solid #1976d2'
                  : '1px solid #e0e0e0',
              '&:hover': { borderColor: '#1976d2' },
            }}
            onClick={() => setCreationMethod(CREATION_METHODS.UPLOAD_DATA)}
          >
            <CardContent
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
              }}
            >
              <UploadFileIcon sx={{ fontSize: 40, mb: 2, color: 'primary.main' }} />
              <Typography variant="h6" gutterBottom>
                Upload Your Data
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Train with your own labeled dataset via a CSV uploaded from your computer or S3
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Synthetic Data Option */}
        <Grid item xs={12} md={4}>
          <Card
            sx={{
              height: '100%',
              cursor: 'pointer',
              border:
                creationMethod === CREATION_METHODS.SYNTHETIC
                  ? '2px solid #1976d2'
                  : '1px solid #e0e0e0',
              '&:hover': { borderColor: '#1976d2' },
            }}
            onClick={() => setCreationMethod(CREATION_METHODS.SYNTHETIC)}
          >
            <CardContent
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
              }}
            >
              <AutoAwesomeIcon sx={{ fontSize: 40, mb: 2, color: 'primary.main' }} />
              <Typography variant="h6" gutterBottom>
                Generate Training Data
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Provide examples and let AI generate training data for your custom extraction needs
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  const renderSelectedMethod = () => {
    if (generatedData.length > 0) {
      return renderGeneratedData();
    }

    switch (creationMethod) {
      // case CREATION_METHODS.PRETRAINED:
      //   return <Typography>Coming Soon</Typography>;
      case CREATION_METHODS.UPLOAD_DATA:
        return (
          <Box sx={{ width: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Upload Training Data
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Upload a CSV file containing your labeled training data. The file should include text
              samples and their corresponding labels.
            </Typography>

            <CSVUpload
              modelName={modelName}
              onSuccess={() => {
                if (!stayOnPage) {
                  router.push('/');
                }
                onCreateModel?.(modelName);
              }}
              onError={(errorMessage: string) => {
                console.error('Error training model:', errorMessage);
              }}
            />
          </Box>
        );
      case CREATION_METHODS.SYNTHETIC:
        return renderSyntheticMethod();
      default:
        return null;
    }
  };

  const renderSyntheticMethod = () => (
    <div>
      <span className="block text-lg font-semibold">Specify Tokens</span>
      <CardDescription>Define your own categories or select existing ones</CardDescription>
      <form onSubmit={(e) => e.preventDefault()}>
        <div className="flex flex-col mt-3">
          {categories.map((category, categoryIndex) => (
            <div key={categoryIndex} className="mb-5 border border-gray-300 p-3 rounded-md">
              <div className="flex justify-between mb-3">
                <TextField
                  className="w-[45%] text-sm"
                  placeholder="Category Name"
                  value={category.name}
                  onChange={(e) => handleCategoryChange(categoryIndex, 'name', e.target.value)}
                  InputProps={{
                    inputProps: {
                      list: `category-options-${categoryIndex}`,
                    },
                  }}
                />
                <datalist id={`category-options-${categoryIndex}`}>
                  {predefinedChoices.map((choice, i) => (
                    <option key={i} value={choice} />
                  ))}
                </datalist>
                <TextField
                  className="w-[45%] text-sm"
                  placeholder="What this category is about."
                  value={category.description}
                  onChange={(e) =>
                    handleCategoryChange(categoryIndex, 'description', e.target.value)
                  }
                />
              </div>
              {category.examples.map((example, exampleIndex) => (
                <div key={exampleIndex} className="flex items-center mb-3">
                  <TextField
                    className="flex-1 text-sm"
                    placeholder={`Example ${exampleIndex + 1}`}
                    value={example.text}
                    onChange={(e) =>
                      handleExampleChange(categoryIndex, exampleIndex, e.target.value)
                    }
                  />
                  <IconButton
                    onClick={() => handleRemoveExample(categoryIndex, exampleIndex)}
                    disabled={category.examples.length === 1}
                  >
                    <DeleteIcon />
                  </IconButton>
                </div>
              ))}
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={() => handleAddExample(categoryIndex)}
                className="mr-3"
              >
                Add Example
              </Button>
              <Button
                variant="contained"
                color="error"
                onClick={() => handleRemoveCategory(categoryIndex)}
                disabled={categories.length === 1}
              >
                Remove Category
              </Button>
            </div>
          ))}
          <Button variant="contained" className="mt-3 w-fit" onClick={handleAddAndReviewCategory}>
            Add Category
          </Button>
          <Button
            variant="contained"
            color={isDataGenerating ? 'success' : 'primary'}
            className="mt-8"
            onClick={generateData}
          >
            {isDataGenerating ? 'Generating data...' : 'Generate data'}
          </Button>
        </div>
      </form>
    </div>
  );

  const renderGeneratedData = () => (
    <>
      <h3 className="text-lg font-semibold mt-5">Categories and Examples</h3>
      <Table className="mt-3">
        <TableHeader>
          <TableRow>
            <TableHead>Category</TableHead>
            <TableHead>Example</TableHead>
            <TableHead>Description</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {categories.map((category, index) => (
            <TableRow key={index}>
              <TableCell className="font-medium">{category.name}</TableCell>
              <TableCell className="font-medium">
                {category.examples.map((ex, i) => (
                  <div key={i}>{ex.text}</div>
                ))}
              </TableCell>
              <TableCell className="font-medium">{category.description}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="mt-5">
        <h3 className="mb-3 text-lg font-semibold">Example Generated Data</h3>
        <div>
          {generatedData.map((pair, index) => (
            <div key={index} className="my-2">
              {renderTaggedSentence(pair)}
            </div>
          ))}
        </div>

        <div className="mt-5 mb-5">
          <h3 className="mb-2 text-lg font-semibold">LLM Provider</h3>
          <Select
            value={llmProvider}
            onChange={(e) => setLLMProvider(e.target.value as LLMProvider)}
            className="w-full"
          >
            <MenuItem value="openai">OpenAI</MenuItem>
            <MenuItem value="self_hosted">Self-hosted LLM</MenuItem>
          </Select>
        </div>

        <div className="flex gap-3 mt-5">
          <Button
            variant="outlined"
            className="flex-1"
            onClick={() => {
              setGeneratedData([]);
              setCreationMethod('');
            }}
          >
            Redefine Tokens
          </Button>
          <Button
            variant="contained"
            className="flex-1"
            onClick={handleCreateNERModel}
            disabled={isLoading}
          >
            {isLoading ? (
              <div className="flex items-center justify-center">
                <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-2" />
                <span>Creating...</span>
              </div>
            ) : (
              'Create'
            )}
          </Button>
        </div>
      </div>
    </>
  );

  return (
    <div>
      {/* App name section */}
      <Box sx={{ mb: 4 }}>
        <span className="block text-lg font-semibold">App Name</span>
        <TextField
          className="text-md w-full"
          value={modelName}
          onChange={(e) => {
            const name = e.target.value;
            setModelName(name);
          }}
          onBlur={(e) => {
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
            // Check if the name contains invalid characters based on the regex pattern
            else if (!regexPattern.test(name)) {
              warningMessage =
                'The app name can only contain letters, numbers, underscores, and hyphens. Please modify the name.';
            }
            // Check if the name already exists in the workflow
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
          disabled={!!appName && !workflowNames.includes(modelName)}
        />
        {warningMessage && (
          <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>
        )}
      </Box>

      <Divider sx={{ my: 4 }} />

      {/* Method selection and content */}
      {renderCreationMethodSelection()}
      {creationMethod && <Divider sx={{ my: 4 }} />}
      {renderSelectedMethod()}
    </div>
  );
};

export default NERQuestions;
