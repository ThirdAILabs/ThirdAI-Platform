import React, { useState } from 'react';
import { Button, TextField, Typography, Stepper, Step, StepLabel, Box } from '@mui/material';
import { useRouter } from 'next/navigation';
import { CardDescription } from '@/components/ui/card';
import { create_knowledge_extraction } from '@/lib/backend';

interface KnowledgeExtractionQuestionsProps {
  workflowNames: string[];
}

enum LlmProvider {
  OpenAI = 'openai',
  OnPrem = 'on-prem',
  SelfHosted = 'self-hosted',
}

const KnowledgeExtractionQuestions: React.FC<KnowledgeExtractionQuestionsProps> = ({
  workflowNames,
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [modelName, setModelName] = useState('');
  const [questions, setQuestions] = useState<string[]>(['']);
  const [llmType, setLlmType] = useState<LlmProvider | null>(null);
  const [warningMessage, setWarningMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const validateAppName = (name: string): string => {
    if (!name) return 'App name is required.';
    if (name.includes(' ')) return 'The app name cannot contain spaces.';
    if (name.includes('.')) return 'The app name cannot contain periods.';
    if (!/^[\w-]+$/.test(name))
      return 'The app name can only contain letters, numbers, underscores, and hyphens.';
    if (workflowNames.includes(name)) return 'An app with this name already exists.';
    return '';
  };

  const handleAddQuestion = () => {
    setQuestions([...questions, '']);
  };

  const handleQuestionChange = (index: number, value: string) => {
    const newQuestions = [...questions];
    newQuestions[index] = value;
    setQuestions(newQuestions);
  };

  const handleSubmit = async () => {
    setIsLoading(true);
    try {
      const params = {
        model_name: modelName,
        questions: questions.map(q => ({ question: q })),
        llm_provider: llmType?.toLowerCase() || '',
        advanced_indexing: true,
        rerank: true,
        generate_answers: true
      };
      
      await create_knowledge_extraction(params);
      router.push('/');
    } catch (error) {
      console.error('Error during workflow creation:', error);
      alert(error instanceof Error ? error.message : 'Failed to create workflow');
      setIsLoading(false);
    }
  };

  const steps = [
    {
      title: 'App Name',
      content: (
        <div className="mt-5">
          <TextField
            className="text-md w-full"
            value={modelName}
            onChange={(e) => {
              const name = e.target.value;
              const warning = validateAppName(name);
              setWarningMessage(warning);
              setModelName(name);
            }}
            placeholder="Enter app name"
          />
          {warningMessage && (
            <span style={{ color: 'red', marginTop: '10px' }}>{warningMessage}</span>
          )}
        </div>
      ),
    },
    {
      title: 'Questions',
      content: (
        <div className="mt-5">
          <CardDescription>Define questions to extract answers from documents</CardDescription>
          {questions.map((question, index) => (
            <div key={index} className="flex gap-4 mt-4">
              <TextField
                className="text-md flex-grow"
                value={question}
                onChange={(e) => handleQuestionChange(index, e.target.value)}
                placeholder={`Question ${index + 1}`}
              />
              {questions.length > 1 && (
                <Button
                  variant="outlined"
                  color="error"
                  onClick={() => {
                    const newQuestions = questions.filter((_, i) => i !== index);
                    setQuestions(newQuestions);
                  }}
                >
                  Delete
                </Button>
              )}
            </div>
          ))}
          <Button onClick={handleAddQuestion} className="mt-4">
            Add Question
          </Button>
        </div>
      ),
    },
    {
      title: 'LLM',
      content: (
        <div className="mt-5">
          <CardDescription>Choose an LLM for extracting answers</CardDescription>
          <div className="flex gap-4 mt-4">
            <Button
              variant={llmType === LlmProvider.OpenAI ? 'contained' : 'outlined'}
              onClick={() => setLlmType(LlmProvider.OpenAI)}
            >
              OpenAI
            </Button>
            <Button
              variant={llmType === LlmProvider.OnPrem ? 'contained' : 'outlined'}
              onClick={() => setLlmType(LlmProvider.OnPrem)}
            >
              On-prem
            </Button>
            <Button
              variant={llmType === LlmProvider.SelfHosted ? 'contained' : 'outlined'}
              onClick={() => setLlmType(LlmProvider.SelfHosted)}
            >
              Self-host
            </Button>
          </div>
        </div>
      ),
    },
  ];

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  return (
    <div>
      <Box sx={{ width: '100%' }}>
        <Stepper activeStep={currentStep}>
          {steps.map((step) => (
            <Step key={step.title}>
              <StepLabel>{step.title}</StepLabel>
            </Step>
          ))}
        </Stepper>
      </Box>

      <div className="mt-8">{steps[currentStep].content}</div>

      <div className="flex justify-end gap-4 mt-8">
        {currentStep > 0 && <Button onClick={handlePrevious}>Previous</Button>}
        {currentStep < steps.length - 1 ? (
          <Button
            onClick={handleNext}
            disabled={currentStep === 0 && (!modelName || !!warningMessage)}
          >
            Next
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={isLoading || !modelName || !llmType || questions.some((q) => !q.trim())}
          >
            {isLoading ? 'Creating...' : 'Create'}
          </Button>
        )}
      </div>
    </div>
  );
};

export default KnowledgeExtractionQuestions;
