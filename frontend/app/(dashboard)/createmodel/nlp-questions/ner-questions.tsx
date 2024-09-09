// app/NERQuestions.js
import React, { useEffect, useState } from 'react';
import { getUsername, trainTokenClassifier, create_workflow, add_models_to_workflow } from '@/lib/backend';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CardDescription } from '@/components/ui/card';

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
  modelGoal: string;
  workflowNames: string[];
  onCreateModel?: (modelId: string) => void;
  stayOnPage?: boolean;
  appName?: string;
};

const NERQuestions = ({ workflowNames, modelGoal, onCreateModel, stayOnPage, appName }: NERQuestionsProps) => {
  const [modelName, setModelName] = useState(!appName ? '' : appName);
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

  const validateCategories = () => {
    // Check if any category has an empty name, example, or description
    return categories.every((category: Category) => {
      return category.name && category.example && category.description;
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
      alert('Error generating data:' + error)
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

  const [isLoading, setIsLoading] = useState(false);

  const handleCreateNERModel = async () => {
    if (!modelName) {
      alert("Please enter a model name.");
      return;
    }
    if (warningMessage !== '') {
      return;
    }
  
    setIsLoading(true);

    try {
      const modelResponse = await trainTokenClassifier(modelName, modelGoal, categories);
      const modelId = modelResponse.data.model_id;

      // This is called from RAG
      if (onCreateModel) {
        onCreateModel(modelId);
      }


      // Create workflow after model creation
      const workflowName = modelName;
      const workflowTypeName = "nlp"; // Assuming this is the type for NER workflows
      const workflowResponse = await create_workflow({ name: workflowName, typeName: workflowTypeName });
      const workflowId = workflowResponse.data.workflow_id;

      // Add the model to the workflow with the appropriate component
      const addModelsResponse = await add_models_to_workflow({
        workflowId,
        modelIdentifiers: [modelId],
        components: ['nlp'], // Specific to this use case
      });

      console.log('Workflow and model addition successful:', addModelsResponse);

      if (!stayOnPage) {
        router.push("/");
      }
    } catch (e) {
      console.log(e || 'Failed to create NER model and workflow');
    } finally {
      setIsLoading(false);
    }
  };

  const [warningMessage, setWarningMessage] = useState("");

  useEffect(()=>{
    console.log('appname', appName)
    if(appName) {
      if (workflowNames.includes(appName)) {
        setWarningMessage("An App with the same name has been created. Please choose a different name.");
      } else {
        setWarningMessage(""); // Clear the warning if the name is unique
      }
    }
  },[appName])

  return (
    <div>
      <span className="block text-lg font-semibold">App Name</span>
      <Input
        className="text-md"
        value={modelName}
        onChange={(e) => {
          const name = e.target.value;
          setModelName(name)
        }}
        onBlur={(e) => {
          const name = e.target.value;
          const regexPattern = /^[\w-]+$/;
          let warningMessage = "";
      
          // Check if the name contains spaces
          if (name.includes(" ")) {
            warningMessage = "The app name cannot contain spaces. Please remove the spaces.";
          } 
          // Check if the name contains periods
          else if (name.includes(".")) {
            warningMessage = "The app name cannot contain periods ('.'). Please remove the periods.";
          } 
          // Check if the name contains invalid characters based on the regex pattern
          else if (!regexPattern.test(name)) {
            warningMessage = "The app name can only contain letters, numbers, underscores, and hyphens. Please modify the name.";
          } 
          // Check if the name already exists in the workflow
          else if (workflowNames.includes(name)) {
            warningMessage = "An app with the same name already exists. Please choose a different name.";
          }
          // Set the warning message or clear it if the name is valid
          setWarningMessage(warningMessage);
          setModelName(name);
        }}
        placeholder="Enter app name"
        style={{ marginTop: "10px" }}
        disabled={!!appName && !workflowNames.includes(modelName)} // Use !! to explicitly convert to boolean
      />
      {warningMessage && (
        <span style={{ color: "red", marginTop: "10px" }}>
          {warningMessage}
        </span>
      )}
      {
        generatedData.length === 0 && <>
          <span className="block text-lg font-semibold" style={{ marginTop: "20px" }}>Specify Tokens</span>
          <CardDescription>Define your own categories or select existing ones</CardDescription>
          <form onSubmit={handleSubmit}>
            <div style={{ display: "flex", flexDirection: "column", marginTop: "10px" }}>

              {categories.map((category, index) => (
                <div  key={index} 
                      style={{ 
                        display: "flex", 
                        flexDirection: "row", 
                        gap: "10px", 
                        justifyContent: "space-between",
                        marginBottom: "10px", // Adds gap between rows
                      }}>
                  <div style={{ width: "100%" }}>
                    <Input
                      list={`category-options-${index}`}
                      style={{ width: "95%" }}
                      className="text-sm"
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
                    style={{ width: "75%" }}
                    className="text-sm"
                    placeholder="Example"
                    value={category.example}
                    onChange={(e) => handleCategoryChange(index, 'example', e.target.value)}
                  />
                  <Input
                    style={{ width: "130%" }}
                    className="text-sm"
                    placeholder="What this category is about."
                    value={category.description}
                    onChange={(e) => handleCategoryChange(index, 'description', e.target.value)}
                  />
                  <Button variant="destructive" onClick={() => handleRemoveCategory(index)}>
                    Remove
                  </Button>
                </div>
              ))}
              <Button style={{ marginTop: "10px", width: "fit-content" }} onClick={handleAddAndReviewCategory}>
                Add Category
              </Button>
              {
                categories.length > 0 &&
                <Button variant={isDataGenerating ? "secondary" : "default"} style={{ marginTop: "30px" }} onClick={generateData}>
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
            <h3 className='text-lg font-semibold' style={{ marginTop: "20px" }}>Categories and Examples</h3>
            <Table style={{ marginTop: "10px" }}>
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

      {!isDataGenerating && generatedData.length > 0 && (
        <div className='mt-5'>
          <h3 className='mb-3 text-lg font-semibold'>Example Generated Data</h3>
          <div>
            {generatedData.map((pair, index) => (
              <div key={index} className='my-2'>
                {renderTaggedSentence(pair)}
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "row", justifyContent: "space-between", gap: "10px", marginTop: "20px" }}>
            <Button variant="outline" style={{ width: "100%" }} onClick={() => setGeneratedData([])}>
              Redefine Tokens
            </Button>
            <Button
              style={{ width: "100%" }}
              onClick={handleCreateNERModel}
              disabled={isLoading}
            >
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-2"></div>
                  <span>Creating...</span>
                </div>
              ) : (
                "Create"
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NERQuestions;
