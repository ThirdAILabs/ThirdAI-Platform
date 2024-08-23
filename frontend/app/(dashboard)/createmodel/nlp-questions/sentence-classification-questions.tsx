// app/NERQuestions.js
import Link from 'next/link';
import React, { useState } from 'react';
import { SelectModel } from '@/lib/db';

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


      const response = await fetch('/api/generate-data-sentence-classification', {
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
    <div className='p-5'>
      <h3 className='mb-3 text-lg font-semibold'>Specify Tokens</h3>
      <form onSubmit={handleSubmit}>
        {categories.map((category, index) => (
          <div key={index} className='flex flex-col md:flex-row md:items-center my-2'>
            <div className="relative w-full md:w-1/3">
              <input
                type="text"
                list={`category-options-${index}`}
                className="form-input w-full px-3 py-2 border rounded-md"
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
            <input
              type="text"
              className='form-input w-full md:w-1/3 md:ml-2 mt-2 md:mt-0 px-3 py-2 border rounded-md'
              placeholder="Example"
              value={category.example}
              onChange={(e) => handleCategoryChange(index, 'example', e.target.value)}
            />
            <button type="button" className='bg-red-500 text-white px-4 py-2 rounded-md md:ml-2 mt-2 md:mt-0' onClick={() => handleRemoveCategory(index)}>
              Remove
            </button>
          </div>
        ))}
        <button type="button" className='bg-blue-500 text-white px-4 py-2 rounded-md mt-2 mr-2' onClick={handleAddAndReviewCategory}>
          Add Category
        </button>
        <button type="button" className='bg-green-500 text-white px-4 py-2 rounded-md mt-2' onClick={() => { setShowReview(true) }}>Finish and Review</button>
      </form>

      {categories.length > 0 && showReview && (
        <div className='mt-5'>
          <h3 className='mb-3 text-lg font-semibold'>Review Categories and Examples</h3>
          <table className='min-w-full bg-white'>
            <thead>
              <tr>
                <th className='py-2 px-4 border-b'>Category Name</th>
                <th className='py-2 px-4 border-b'>Example</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((category, index) => (
                <tr key={index}>
                  <td className='py-2 px-4 border-b'>{category.name}</td>
                  <td className='py-2 px-4 border-b'>{category.example}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <button className='bg-blue-500 text-white px-4 py-2 rounded-md mt-2' onClick={generateData}>Generate more data</button>
        </div>
      )}

      {isDataGenerating && (
        <div className='flex justify-center mt-5'>
          <div className='animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500'></div>
        </div>
      )}

      {!isDataGenerating && generatedData.length > 0 && (
        <div className='mt-5'>
          <h3 className='mb-3 text-lg font-semibold'>Generated Data</h3>

          <table className='table'>
            <thead>
              <tr>
                <th>Category</th>
                <th>Generated Examples</th>
              </tr>
            </thead>
            <tbody>
              {generatedData.map((data, index) => (
                <tr key={index}>
                  <td>{data.category}</td>
                  <td>
                    <ul>
                      {data.examples.map((example, i) => (
                        <li key={i}>{example}</li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex justify-center">
            <Link href="/">
              <button
                type="button"
                className="mb-4 bg-blue-500 text-white px-4 py-2 rounded-md"
                onClick={async () => { }}
              >
                Create
              </button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};

export default SCQQuestions;
