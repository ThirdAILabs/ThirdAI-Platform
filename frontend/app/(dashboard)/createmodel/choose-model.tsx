'use client';

import { useState, useEffect } from 'react';
import EnterpriseSearchQuestions from './rag-questions/enterprise-search-questions';
import ChatbotQuestions from './rag-questions/chatbot-questions';
import NLPQuestions from './nlp-questions/nlp-questions';
import KnowledgeExtractionQuestions from './knowledge-extraction/knowledge-extraction-questions';
import { fetchWorkflows, Workflow } from '@/lib/backend';
import { Typography, Box, Divider, Select, MenuItem, FormControl } from '@mui/material';

const USE_CASES = [
  {
    name: 'Knowledge Extraction',
    value: 'knowledge-extraction',
    description: 'Extract structured answers to specific questions from your document collection',
  },
  {
    name: 'Enterprise Search',
    value: 'enterprise-search',
    description: 'Build a search engine that understands context and meaning in your documents',
  },
  {
    name: 'Chatbot',
    value: 'chatbot',
    description:
      'Create an AI assistant that can engage in conversations and answer questions using your data',
  },
  {
    name: 'NLP / Text Analytics',
    value: 'nlp-text-analytics',
    description: 'Extract insights, classify content, and analyze unstructured text data at scale',
  },
];

export default function ChooseProblem() {
  const [modelType, setModelType] = useState('');
  const [privateModels, setPrivateModels] = useState<Workflow[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  useEffect(() => {
    async function getModels() {
      try {
        const response = await fetchWorkflows();
        setPrivateModels(response);
        setWorkflows(response);
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

  const workflowNames = workflows.map((workflow) => workflow.model_name);

  const handleChange = (event: any) => {
    setModelType(event.target.value);
  };

  return (
    <Box className="flex flex-col gap-8">
      <Box>
        <Typography variant="h6" className="mb-2">
          Use case
        </Typography>
        <Typography variant="body2" className="text-gray-500 mb-4">
          Please select the app type based on your use case.
        </Typography>

        <FormControl fullWidth>
          <Select
            value={modelType}
            onChange={handleChange}
            displayEmpty
            sx={{
              '& .MuiSelect-select': {
                padding: '16px',
              },
              '& .MuiListSubheader-root': {
                lineHeight: '1.2',
                padding: '16px',
              },
              '& .MuiMenuItem-root': {
                padding: '16px',
              },
            }}
            renderValue={(selected) => {
              if (!selected) {
                return <Typography color="text.secondary">Select a use case</Typography>;
              }
              const selectedCase = USE_CASES.find((useCase) => useCase.value === selected);
              return selectedCase?.name;
            }}
          >
            {USE_CASES.map((useCase) => (
              <MenuItem key={useCase.value} value={useCase.value}>
                <Box>
                  <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                    {useCase.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {useCase.description}
                  </Typography>
                </Box>
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {modelType && (
        <Box className="w-full">
          <Divider className="mb-6" />
          {modelType === 'chatbot' && (
            <ChatbotQuestions models={privateModels} workflowNames={workflowNames} />
          )}
          {modelType === 'nlp-text-analytics' && <NLPQuestions workflowNames={workflowNames} />}
          {modelType === 'enterprise-search' && (
            <EnterpriseSearchQuestions models={privateModels} workflowNames={workflowNames} />
          )}
          {modelType === 'knowledge-extraction' && (
            <KnowledgeExtractionQuestions workflowNames={workflowNames} />
          )}
        </Box>
      )}
    </Box>
  );
}
