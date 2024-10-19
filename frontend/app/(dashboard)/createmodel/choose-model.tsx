'use client';

import { useState, useEffect } from 'react';
import RAGQuestions from './rag-questions';
import NLPQuestions from './nlp-questions/nlp-questions';
import DocumentClassificationQuestions from './document-class-questions';
import SemanticSearchQuestions from './semantic-search-questions';
import TabularClassificationQuestions from './tabular-class-questions';
import { fetchWorkflows, Workflow } from '@/lib/backend';
import { Divider } from '@mui/material';
import { CardDescription } from '@/components/ui/card';
import DropdownMenu from '@/components/ui/dropDownMenu';
export default function ChooseProblem() {
  const [modelType, setModelType] = useState('');

  const [privateModels, setPrivateModels] = useState<Workflow[]>([]);

  useEffect(() => {
    async function getModels() {
      try {
        const response = await fetchWorkflows();
        setPrivateModels(response);
      } catch (err) {
        if (err instanceof Error) {
          console.log(err.message);
        } else {
          console.log('An unknown error occurred');
        }
      }
    }

    getModels();
  }, []);

  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  useEffect(() => {
    async function getWorkflows() {
      try {
        const fetchedWorkflows = await fetchWorkflows();
        console.log('workflows', fetchedWorkflows);
        setWorkflows(fetchedWorkflows);
      } catch (err) {
        if (err instanceof Error) {
          console.log(err.message);
        } else {
          console.log('An unknown error occurred');
        }
      }
    }

    getWorkflows();
  }, []);

  const workflowNames = workflows.map((workflow) => workflow.model_name);

  // Updated Use Case names
  const ENTERPRISE_SEARCH = 'Enterprise Search';
  const NLP_TEXT_ANALYSIS = 'NLP / Text Analytics';
  const CHATBOT = 'Chatbot';

  // const DOC_CLASSIFICATION = "Document Classification";
  // const TABULAR_CLASSIFICATION = "Tabular Classification";

  // Update the useCases array with new names
  const useCases = [{ name: ENTERPRISE_SEARCH }, { name: CHATBOT }, { name: NLP_TEXT_ANALYSIS }];
  const handleSetModelType = (model: string) => {
    setModelType(model);
  };

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span className="block text-lg font-semibold">Use case</span>
        <CardDescription>Please select the app type based on your use case.</CardDescription>
        <div style={{ marginTop: '10px' }}>
          <DropdownMenu
            title="Select a use case"
            handleSelectedTeam={handleSetModelType}
            teams={useCases}
          />
        </div>

        {modelType && (
          <div style={{ width: '100%', marginTop: '20px' }}>
            <Divider style={{ marginBottom: '20px' }} />
            {modelType === CHATBOT && (
              <RAGQuestions models={privateModels} workflowNames={workflowNames} isChatbot={true} />
            )}
            {modelType === NLP_TEXT_ANALYSIS && <NLPQuestions workflowNames={workflowNames} />}
            {modelType === ENTERPRISE_SEARCH && (
              <RAGQuestions
                models={privateModels}
                workflowNames={workflowNames}
                isChatbot={false}
              />
              // <SemanticSearchQuestions models={privateModels} workflowNames={workflowNames} />
            )}
            {/* {modelType === DOC_CLASSIFICATION && <DocumentClassificationQuestions workflowNames={workflowNames} />} */}
            {/* {modelType === TABULAR_CLASSIFICATION && <TabularClassificationQuestions workflowNames={workflowNames} />} */}
          </div>
        )}
      </div>
    </>
  );
}
