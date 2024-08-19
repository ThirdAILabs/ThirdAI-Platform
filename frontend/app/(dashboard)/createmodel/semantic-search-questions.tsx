import React, { useState } from 'react';
import { getUsername, train_ndb, create_workflow, add_models_to_workflow } from '@/lib/backend';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CardDescription } from '@/components/ui/card';
import { useRouter } from 'next/navigation';

interface SemanticSearchQuestionsProps {
  onCreateModel?: (modelID: string) => void;
  stayOnPage?: boolean;
};

enum SourceType {
  S3 = "s3",
  LOCAL = "local",
}

const SemanticSearchQuestions = ({ onCreateModel, stayOnPage }: SemanticSearchQuestionsProps) => {
    const [modelName, setModelName] = useState('');
    const [sources, setSources] = useState<Array<{ type: string, value: File | null }>>([]);
    const router = useRouter();
    
    const addSource = (type: SourceType) => {
      setSources(prev => [...prev, {type, value: null}]);
    }

    const setSourceValue = (index: number, value: File) => {
      const newSources = [...sources];
      newSources[index].value = value;
      setSources(newSources);
    }
  
    const deleteSource = (index: number) => {
      const updatedSources = sources.filter((_, i) => i !== index);
      setSources(updatedSources);
    };

    const makeFileFormData = () => {
      let formData = new FormData();
      const fileDetailsList: Array<{ mode: string; location: string }> = [];

      sources.filter(({value}) => !!value).forEach(({type, value}) => {
        formData.append('files', value!); // Assert that value is non-null since we've filtered nulls.
        fileDetailsList.push({ mode: 'unsupervised', location: type });
      });
  
      const extraOptionsForm = { retriever: 'finetunable_retriever' };
      formData.append('extra_options_form', JSON.stringify(extraOptionsForm));
      formData.append('file_details_list', JSON.stringify({ file_details: fileDetailsList }));

      return formData;
    };

    const submit = async () => {
      try {
        if (!modelName) {
          alert("Please give the app a name. The name cannot have spaces, forward slashes (/) or colons (:).")
          return;
        }
        if (modelName.includes(" ") || modelName.includes("/") || modelName.includes(":")) {
          alert("The app name cannot have spaces, forward slashes (/) or colons (:).")
          return;
        }

        console.log(`Submitting model '${modelName}'`);

        const formData = makeFileFormData();

        // Print out all the FormData entries
        formData.forEach((value, key) => {
          console.log(`${key}:`, value);
        });

        console.log('modelName', modelName)

        // Step 1: Create the model
        const modelResponse = await train_ndb({ name: modelName, formData });
        const modelId = modelResponse.data.model_id;

        // This is called from RAG
        if (onCreateModel) {
          onCreateModel(modelId);
        }

        // Step 2: Create the workflow
        const workflowName = modelName;
        const workflowTypeName = "semantic_search"; // You can change this as needed
        const workflowResponse = await create_workflow({ name: workflowName, typeName: workflowTypeName });
        const workflowId = workflowResponse.data.workflow_id;

        // Step 3: Add the model to the workflow
        const addModelsResponse = await add_models_to_workflow({
            workflowId,
            modelIdentifiers: [modelId],
            components: ["search"] // Adjust components as needed
        });

        console.log('addModelsResponse', addModelsResponse);

        if (!stayOnPage) {
          router.push("/")
        }
    } catch (error) {
        console.log(error);
    }
  }

    console.log(sources);

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

        <span className="block text-lg font-semibold" style={{marginTop: "20px"}}>Sources</span>
        <CardDescription>Select files to search over.</CardDescription>
        
        {
          sources.map(({type}, index) => (
            <div>
              <div style={{display: "flex", flexDirection: "row", gap: "20px", justifyContent: "space-between", marginTop: "10px"}}>
                {type === SourceType.S3 && (
                  <Input 
                    className="text-md"
                    onChange={(e) => setSourceValue(index, new File([], e.target.value))}
                    placeholder="http://s3.amazonaws.com/bucketname/"
                  />
                )}
                {type === SourceType.LOCAL && (
                  <Input
                    type="file"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setSourceValue(index, e.target.files[0]);
                      }
                    }}
                    multiple
                  />
                )}
                <Button
                  variant="destructive"
                  onClick={() => deleteSource(index)}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))
        }

        <div style={{display: "flex", gap: "10px", marginTop: "10px"}}>
          <Button onClick={() => addSource(SourceType.LOCAL)}>Add Local File</Button>
          <Button onClick={() => addSource(SourceType.S3)}>Add S3 File</Button>
        </div>

        <div className="flex justify-start">
          <Button onClick={submit} style={{marginTop: "30px", width: "100%"}}>
            Create
          </Button>
        </div>
      </div>
    );
};

export default SemanticSearchQuestions;
