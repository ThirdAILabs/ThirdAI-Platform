// app/NERQuestions.js
import Link from 'next/link';
import React, { useState } from 'react';
import { SelectModel } from '@/lib/db';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface SCQQuestionsProps {
  question: string;
  answer: string;
}

type Category = {
  name: string;
  example: string;
};

type GeneratedData = {
  category: string;
  examples: string[];
};

const predefinedChoices = [
  'Positive Sentiment',
  'Negative Sentiment',
];

const SCQQuestions = ({ question, answer }: SCQQuestionsProps) => {
  const [categories, setCategories] = useState([{ name: '', example: '' }]);
  const [showReview, setShowReview] = useState(false);
  const [isDataGenerating, setIsDataGenerating] = useState(false);
  const [generatedData, setGeneratedData] = useState<GeneratedData[]>([]);
  const [generateDataPrompt, setGenerateDataPrompt] = useState('');

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
    setCategories([...categories, { name: '', example: '' }]);
  };

  const handleRemoveCategory = (index: number) => {
    setCategories(categories.filter((_, i) => i !== index));
  };

  const validateCategories = () => {
    // Check if any category has an empty name or example
    return categories.every((category: Category) => {
      return category.name && category.example
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

      console.log('sending question', question)
      console.log('sending answer', answer)
      console.log('sending categories', categories)


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
      alert('Error generating data:' + error)
      setIsDataGenerating(false);
    }
  };

  const renderTaggedSentence = (pair: { sentence: string; nerData: string[] }) => {
    return pair.sentence.split(' ').map((token, idx) => {
      const tag = pair.nerData[idx];
      if (tag === 'O') {
        return (
          <span key={idx} style={{ padding: '0 4px' }}>
            {token}
          </span>
        );
      }
      return (
        <span key={idx} style={{ padding: '0 4px', backgroundColor: tag === 'AGE' ? '#ffcccb' : '#ccffcc', borderRadius: '4px' }}>
          {token} <span style={{ fontSize: '0.8em', fontWeight: 'bold', color: tag === 'AGE' ? '#ff0000' : '#00cc00' }}>{tag}</span>
        </span>
      );
    });
  };

  return (
    <div>
      <span className="block text-lg font-semibold">Specify Tokens</span>
      <form onSubmit={handleSubmit} style={{ marginTop: "20px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {categories.map((category, index) => (
            <div
              key={index}
              style={{
                display: "flex",
                flexDirection: "row",
                gap: "10px",
                justifyContent: "space-between",
              }}
            >
              <div style={{ width: "100%" }}>
                <Input
                  list={`category-options-${index}`}
                  style={{ width: "100%" }}
                  className="text-md"
                  placeholder="Category Name"
                  value={category.name}
                  onChange={(e) => handleCategoryChange(index, "name", e.target.value)}
                />
                <datalist id={`category-options-${index}`}>
                  {predefinedChoices.map((choice, i) => (
                    <option key={i} value={choice} />
                  ))}
                </datalist>
              </div>
              <Input
                style={{ width: "100%" }}
                className="text-md"
                placeholder="Example"
                value={category.example}
                onChange={(e) => handleCategoryChange(index, "example", e.target.value)}
              />
              <Button
                variant="destructive"
                onClick={() => handleRemoveCategory(index)}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button
            style={{ marginTop: "10px", width: "fit-content" }}
            onClick={handleAddAndReviewCategory}
          >
            Add Category
          </Button>
          {categories.length > 0 && (
            <Button
              variant={isDataGenerating ? "secondary" : "default"}
              style={{ marginTop: "30px" }}
              onClick={generateData}
            >
              {isDataGenerating ? "Generating data..." : "Generate data"}
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
          <Table style={{ marginTop: "10px" }}>
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
              display: "flex",
              flexDirection: "row",
              justifyContent: "space-between",
              gap: "10px",
              marginTop: "20px",
            }}
          >
            <Button
              variant="outline"
              style={{ width: "100%" }}
              onClick={() => setGeneratedData([])}
            >
              Redefine Tokens
            </Button>
            <Button style={{ width: "100%" }} onClick={()=>{}}>
              Create
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SCQQuestions;
