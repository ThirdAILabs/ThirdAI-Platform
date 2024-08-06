// app/NERQuestions.js
import React, { useState } from 'react';
import { trainTokenClassifier } from '@/lib/backend';
import { useRouter } from 'next/navigation';

type Category = {
  name: string;
  example: string;
  description: string;
};

const predefinedChoices = [
  'PHONENUMBER',
  'SSN',
  'CREDITCARDNUMBER',
  'LOCATION',
  'NAME'
];

interface NERQuestionsProps {
  onCreateModel?: (userName: string, modelName: string) => void;
  stayOnPage?: boolean;
};

const NERQuestions = ({ onCreateModel, stayOnPage }: NERQuestionsProps) => {
  const [modelName, setModelName] = useState("");
  const [categories, setCategories] = useState([{ name: '', example: '', description: '' }]);
  const [showReview, setShowReview] = useState(false);
  const [isDataGenerating, setIsDataGenerating] = useState(false);
  const [generatedData, setGeneratedData] = useState([]);
  const [generateDataPrompt, setGenerateDataPrompt] = useState('');
  
  const router = useRouter();

  const handleCategoryChange = (index: number, field: keyof Category, value: string) => {
    const updatedCategories = [...categories];
    updatedCategories[index][field] = value;
    setCategories(updatedCategories);
  };

  const handleAddCategory = () => {
    setCategories([...categories, { name: '', example: '', description: '' }]);
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

    try {
      setIsDataGenerating(true);

      const response = await fetch('/api/generate-data-token-classification', {
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
      <h3 className='mb-3 text-lg font-semibold'>Model Name</h3>
      <input
        type="text"
        className="form-input w-full px-3 py-2 border rounded-md"
        placeholder="Model Name"
        value={modelName}
        onChange={(e) => setModelName(e.target.value)}
      />
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
            <input
              type="text"
              className='form-input w-full md:w-1/3 md:ml-2 mt-2 md:mt-0 px-3 py-2 border rounded-md'
              placeholder="What this category is about."
              value={category.description}
              onChange={(e) => handleCategoryChange(index, 'description', e.target.value)}
            />
            <button type="button" className='bg-red-500 text-white px-4 py-2 rounded-md md:ml-2 mt-2 md:mt-0' onClick={() => handleRemoveCategory(index)}>
              Remove
            </button>
          </div>
        ))}
        <button type="button" className='bg-blue-500 text-white px-4 py-2 rounded-md mt-2 mr-2' onClick={handleAddCategory}>
          Add Category
        </button>
        <button type="button" className='bg-green-500 text-white px-4 py-2 rounded-md mt-2' onClick={()=>{setShowReview(true)}}>Finish and Review</button>
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

      {! isDataGenerating && generatedData.length > 0 && (
        <div className='mt-5'>
          <h3 className='mb-3 text-lg font-semibold'>Generated Data</h3>
          <div>
            {generatedData.map((pair, index) => (
              <div key={index} className='my-2'>
                {renderTaggedSentence(pair)}
              </div>
            ))}
          </div>

          <div className="flex justify-center">
            <button
              type="button"
              className="mb-4 bg-blue-500 text-white px-4 py-2 rounded-md"
              onClick={() => {
                if (!modelName) {
                  alert("Please enter a model name.");
                  return;
                }
                const tags = Array.from(new Set(categories.map(cat => cat.name)));
                // TODO: We need a better naming scheme, or add a place to enter the model name.
                if (onCreateModel) {
                  // TODO: SOMEHOW GET USERNAME
                  onCreateModel('peter', modelName);
                }
                trainTokenClassifier(modelName, generatedData, tags).then(() => {
                  if (!stayOnPage) {
                    router.push("/");
                  }
                }).catch(e => {
                  alert(e);
                });

              }}
            >
              Create
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NERQuestions;
