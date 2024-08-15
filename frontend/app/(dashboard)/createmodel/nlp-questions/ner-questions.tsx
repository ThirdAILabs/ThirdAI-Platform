// app/NERQuestions.js
import React, { useState } from 'react';
import { getUsername, trainTokenClassifier } from '@/lib/backend';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

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
    for (const category of categories) {
      if (category.name === "" || category.example === "" || category.description === "") {
        alert("All tokens must have a name, example, and description.");
        return;
      }
    }

    if (isDataGenerating) {
      return;
    }

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
          <>
            <span key={idx} style={{ padding: '0 4px' }}>
              {token}
            </span>
            {' '}
          </>
        );
      }
      return (
        <>
          <span key={idx} style={{ padding: '0 4px', backgroundColor: tag === 'AGE' ? '#ffcccb' : '#ccffcc', borderRadius: '4px' }}>
            {token} <span style={{ fontSize: '0.8em', fontWeight: 'bold', color: tag === 'AGE' ? '#ff0000' : '#00cc00' }}>{tag}</span>
          </span>
          {' '}
        </>
      );
    });
  };

  const createModel = () => {
    if (!modelName) {
      alert("Please enter a model name.");
      return;
    }
    const tags = Array.from(new Set(categories.map(cat => cat.name)));
    // TODO: We need a better naming scheme, or add a place to enter the model name.
    if (onCreateModel) {
      // TODO: SOMEHOW GET USERNAME
      onCreateModel(getUsername(), modelName);
    }
    trainTokenClassifier(modelName, generatedData, tags).then(() => {
      if (!stayOnPage) {
        router.push("/");
      }
    }).catch(e => {
      alert(e);
    });

  }

  return (
    <div>
      <span className="block text-lg font-semibold">App Name</span>
      <Input
        className="text-md"
        value={modelName}
        onChange={(e) => setModelName(e.target.value)}
        placeholder="Enter app name"
        style={{marginTop: "10px"}}
      />
      {
        generatedData.length === 0 && <>
          <span className="block text-lg font-semibold" style={{marginTop: "20px"}}>Specify Tokens</span>
          <form onSubmit={handleSubmit}>
            <div style={{display: "flex", flexDirection: "column", marginTop: "10px"}}>

              {categories.map((category, index) => (
                <div key={index} style={{display: "flex", flexDirection: "row", gap: "10px", justifyContent: "space-between"}}>
                  <div style={{width: "100%"}}>
                    <Input
                      list={`category-options-${index}`}
                      style={{width: "100%"}}
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
                    style={{width: "100%"}}
                    className="text-md"
                    placeholder="Example"
                    value={category.example}
                    onChange={(e) => handleCategoryChange(index, 'example', e.target.value)}
                  />
                  <Input
                    style={{width: "100%"}}
                    className="text-md"
                    placeholder="What this category is about."
                    value={category.description}
                    onChange={(e) => handleCategoryChange(index, 'description', e.target.value)}
                  />
                  <Button variant="destructive" onClick={() => handleRemoveCategory(index)}>
                    Remove
                  </Button>
                </div>
              ))}
              <Button style={{marginTop: "10px", width: "fit-content"}} onClick={handleAddCategory}>
                Add Category
              </Button>
              {
                categories.length > 0 &&
                <Button variant={isDataGenerating ? "secondary" : "default"} style={{marginTop: "30px"}} onClick={generateData}>
                  {isDataGenerating ? "Generating data..." : "Generate data"}
                </Button>
              }
            </div>
          </form>
        </>
      }

      {isDataGenerating && (
        <div className='flex justify-center mt-5'>
          <div className='animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500'></div>
        </div>
      )}

      {
        generatedData.length > 0 && (
          <>
            <h3 className='text-lg font-semibold' style={{marginTop: "20px"}}>Categories and Examples</h3>
            <Table style={{marginTop: "10px"}}>
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
                    <TableCell className="font-medium" align="left">{category.name}</TableCell>
                    <TableCell className="font-medium" align="left">{category.example}</TableCell>
                    <TableCell className="font-medium" align="left">{category.description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )
      }

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

          <div style={{display: "flex", flexDirection: "row", justifyContent: "space-between", gap: "10px", marginTop: "20px"}}>
            <Button variant="outline" style={{width: "100%"}} onClick={() => setGeneratedData([])}>
              Redefine Tokens
            </Button>
            <Button style={{width: "100%"}} onClick={createModel}>
              Create
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NERQuestions;
