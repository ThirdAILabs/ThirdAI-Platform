'use client';

import { useState, useEffect } from 'react';
import { SelectModel } from '@/lib/db';
import RAGQuestions from './rag-questions';
import NLPQuestions from './nlp-questions/nlp-questions';
import DocumentClassificationQuestions from './document-class-questions';
import SemanticSearchQuestions from './semantic-search-questions';
import TabularClassificationQuestions from './tabular-class-questions';
import {
  fetchPublicModels,
  fetchPrivateModels,
  fetchPendingModels,
  fetchWorkflows,
  Workflow,
} from '@/lib/backend';
import { Divider } from '@mui/material';
import { CardDescription } from '@/components/ui/card';

export default function ChooseProblem() {
  const [modelType, setModelType] = useState('');

  const [privateModels, setPrivateModels] = useState<SelectModel[]>([]);
  const [pendingModels, setPendingModels] = useState<SelectModel[]>([]);

  useEffect(() => {
    async function getModels() {
      try {
        let response = await fetchPublicModels('');
        const publicModels = response.data;
        console.log('publicModels', publicModels);

        response = await fetchPrivateModels('');
        const privateModels: SelectModel[] = response.data;
        setPrivateModels(privateModels);

        response = await fetchPendingModels();
        const pendingModels = response.data; // Extract the data field
        console.log('pendingModels', pendingModels);
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

  const workflowNames = workflows.map((workflow) => workflow.name);

  const RETRIEVAL = 'Retrieval';
  const NLP = 'Natural Language Processing';
  const RAG = 'Retrieval Augmented Generation';
  // const DOC_CLASSIFICATION = "Document Classification";
  // const TABULAR_CLASSIFICATION = "Tabular Classification";

  // const useCases = [RETRIEVAL, NLP, RAG, DOC_CLASSIFICATION, TABULAR_CLASSIFICATION];
  const useCases = [RETRIEVAL, NLP, RAG];

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span className="block text-lg font-semibold">Use case</span>
        <CardDescription>Please select the app type based on your use case.</CardDescription>
        <div style={{ marginTop: '10px' }}>
          <select
            value={modelType || ''}
            onChange={(e) => setModelType(e.target.value)}
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '16px',
              border: '1px solid #ccc',
              borderRadius: '4px',
            }}
          >
            <option value="" disabled>
              Select a use case
            </option>
            {useCases.map((type, index) => (
              <option key={index} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>

        {modelType && (
          <div style={{ width: '100%', marginTop: '20px' }}>
            <Divider style={{ marginBottom: '20px' }} />
            {modelType === RAG && (
              <RAGQuestions models={privateModels} workflowNames={workflowNames} />
            )}
            {modelType === NLP && <NLPQuestions workflowNames={workflowNames} />}
            {modelType === RETRIEVAL && <SemanticSearchQuestions workflowNames={workflowNames} />}
            {/* {modelType === DOC_CLASSIFICATION && <DocumentClassificationQuestions workflowNames={workflowNames} />} */}
            {/* {modelType === TABULAR_CLASSIFICATION && <TabularClassificationQuestions workflowNames={workflowNames} />} */}
          </div>
        )}
      </div>
    </>
  );
}
