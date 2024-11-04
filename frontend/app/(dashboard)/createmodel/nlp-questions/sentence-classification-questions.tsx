// app/NERQuestions.js
import Link from 'next/link';
import React, { useState } from 'react';
import { Button } from '@mui/material';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { trainSentenceClassifier } from '@/lib/backend';
import { useRouter } from 'next/navigation';

interface SCQQuestionsProps {
  question: string;
  answer: string;
  workflowNames: string[];
}

type Category = {
  name: string;
  example: string;
  description: string;
};

type GeneratedData = {
  category: string;
  examples: string[];
};

const predefinedChoices = ['POSITIVE_SENTIMENT', 'NEGATIVE_SENTIMENT'];

const SCQQuestions = ({ question, answer, workflowNames }: SCQQuestionsProps) => {
  const [modelName, setModelName] = useState('');
  const [warningMessage, setWarningMessage] = useState('');
  const [categories, setCategories] = useState([{ name: '', example: '', description: '' }]);
  const [showReview, setShowReview] = useState(false);
  const [isDataGenerating, setIsDataGenerating] = useState(false);
  const [generatedData, setGeneratedData] = useState<GeneratedData[]>([]);
  const [generateDataPrompt, setGenerateDataPrompt] = useState('');

  const router = useRouter();

  const handleCategoryChange = (index: number, field: string, value: string) => {
    const newCategories = categories.map((category, i) => {
      if (i === index) {
        return { ...category, [field]: value };
      }
      return category;
    });
    setCategories(newCategories);
  };

  const handleAddCategory = () => {
    setCategories([...categories, { name: '', example: '', description: '' }]);
  };

  const handleRemoveCategory = (index: number) => {
    setCategories(categories.filter((_, i) => i !== index));
  };

  const validateCategories = () => {
    // Check if any category has an empty name or example
    return categories.every((category: Category) => {
      return category.name && category.example && category.description;
    });
  };

  const validateLabels = () => {
    // ensure that category.name does not contain space
    return categories.every((category: Category) => {
      return !category.name.includes(' ');
    });
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    console.log('Categories and examples:', categories);
    // Handle the submission logic here

    setShowReview(true);
  };

  const handleReview = () => {
    if (validateCategories()) {
      if (validateLabels()) {
        setShowReview(true);
        return true;
      } else {
        alert('CategoryName field should not have any space.');
        return false;
      }
    } else {
      alert('All fields (CategoryName, Example) must be filled for each category.');
      return false;
    }
  };

  const handleAddAndReviewCategory = () => {
    const reviewSuccess = handleReview();
    if (reviewSuccess) {
      handleAddCategory();
    }
  };

  const generateData = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();

    try {
      setIsDataGenerating(true);

      console.log('sending question', question);
      console.log('sending answer', answer);
      console.log('sending categories', categories);

      const response = await fetch('/endpoints/generate-data-sentence-classification', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question, answer, categories }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Network response was not ok');
      }

      const result = await response.json();

      console.log('result', result);
      setGeneratedData(result.generatedExamples);
      setGenerateDataPrompt(result.prompts);

      setIsDataGenerating(false);
    } catch (error) {
      console.error('Error generating data:', error);
      alert('Error generating data:' + error);
      setIsDataGenerating(false);
    }
  };

  const handleCreateSCModel = async () => {
    if (!modelName) {
      alert('Please enter a model name.');
      return;
    }
    if (warningMessage !== '') {
      return;
    }

    try {
      const modelResponse = await trainSentenceClassifier(
        modelName,
        /* modelGoal= */ question,
        /* examples= */ categories
      );

      console.log('created text classification model: ', modelResponse.data.model_id);

      router.push('/');
    } catch (e) {
      console.log(e || 'Failed to create NER model and workflow');
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
          setModelName(name);
        }}
        onBlur={(e) => {
          const name = e.target.value;
          if (workflowNames.includes(name)) {
            setWarningMessage(
              'A workflow with the same name has been created. Please choose a different name.'
            );
          } else {
            setWarningMessage(''); // Clear the warning if the name is unique
          }
        }}
        placeholder="Enter app name"
        style={{ marginTop: '10px' }}
      />
      {warningMessage && <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>}
      <span className="block text-lg font-semibold" style={{ marginTop: '20px' }}>
        Specify Classes
      </span>
      <form onSubmit={handleSubmit} style={{ marginTop: '10px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {categories.map((category, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                flexDirection: 'row',
                gap: '10px',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ width: '100%' }}>
                <Input
                  list={`category-options-${index}`}
                  style={{ width: '100%' }}
                  className="text-md"
                  placeholder="Category Name"
                  value={category.name}
                  onChange={(e) => handleCategoryChange(index, 'name', e.target.value)}
                />
                <datalist id={`category-options-${index}`}>
                  {predefinedChoices.map((choice, i) => (
                    <option key={i} value={choice} />
                  ))}
                </datalist>
              </div>
              <Input
                style={{ width: '100%' }}
                className="text-md"
                placeholder="Example"
                value={category.example}
                onChange={(e) => handleCategoryChange(index, 'example', e.target.value)}
              />
              <Input
                style={{ width: '100%' }}
                className="text-md"
                placeholder="Description"
                value={category.description}
                onChange={(e) => handleCategoryChange(index, 'description', e.target.value)}
              />
              <Button variant="contained" color="error" onClick={() => handleRemoveCategory(index)}>
                Remove
              </Button>
            </div>
          ))}
          <Button
            style={{ marginTop: '10px', width: 'fit-content' }}
            onClick={handleAddAndReviewCategory}
            variant="contained"
          >
            Add Category
          </Button>
          {categories.length > 0 && (
            <Button
              variant="contained"
              style={{ marginTop: '30px' }}
              onClick={generateData}
              color={isDataGenerating ? 'success' : 'primary'}
            >
              {isDataGenerating ? 'Generating data...' : 'Generate data'}
            </Button>
          )}
        </div>
      </form>

      {isDataGenerating && (
        <div className="flex justify-center mt-5">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      )}

      {!isDataGenerating && generatedData.length > 0 && (
        <div className="mt-5">
          <h3 className="mb-3 text-lg font-semibold">Generated Data</h3>
          <Table style={{ marginTop: '10px' }}>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Generated Examples</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {generatedData.map((data, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium" align="left">
                    {data.category}
                  </TableCell>
                  <TableCell className="font-medium" align="left">
                    <ul>
                      {data.examples.map((example, i) => (
                        <li key={i}>{example}</li>
                      ))}
                    </ul>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div
            style={{
              display: 'flex',
              flexDirection: 'row',
              justifyContent: 'space-between',
              gap: '10px',
              marginTop: '20px',
            }}
          >
            <Button
              variant="outlined"
              style={{ width: '100%' }}
              onClick={() => setGeneratedData([])}
            >
              Redefine Tokens
            </Button>
            <Button style={{ width: '100%' }} onClick={handleCreateSCModel} variant="contained">
              Create
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SCQQuestions;
