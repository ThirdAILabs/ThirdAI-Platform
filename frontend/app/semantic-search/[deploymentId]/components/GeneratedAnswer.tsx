import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { color, fontSizes } from '../stylingConstants';
import { Spacer } from './Layout';
import MoreInfo from './MoreInfo';
import ReactMarkdown from 'react-markdown';
import TypingAnimation from './TypingAnimation';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faStop } from '@fortawesome/free-solid-svg-icons';
import { Alert, AlertTitle } from '@mui/material';

interface LLMErrorProps {
  open: boolean;
}

const LLMErrorNotification: React.FC<LLMErrorProps> = ({ open }) => {
  if (!open) return null;

  return (
    <Alert severity="error" className="fixed top-4 right-4 shadow-lg z-[2000] w-96">
      <AlertTitle>LLM Generation Failed</AlertTitle>
      Please notify admin to reconfigure this app's LLM endpoint.
    </Alert>
  );
};

interface GeneratedAnswerProps {
  answer: string;
  regenerateAndBypassCache?: () => void;
  queryInfo?: {
    cachedQuery: string;
    userQuery: string;
    isDifferent: boolean;
  } | null;
  cacheEnabled: boolean;
  setCacheEnabled: (enabled: boolean) => void;
  abortController: AbortController | null;
  setAbortController: (controller: AbortController | null) => void;
  setAnswer: (answer: string) => void;
}

// Styled component for the button
const PauseButton = styled.button`
  width: 40px; /* Ensure the width is equal to the height */
  height: 40px; /* Ensures the button remains a circle */
  background-color: black;
  border: none;
  border-radius: 50%; /* This makes it a circle */
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;
  box-sizing: border-box; /* Ensures padding and border don't affect the circle size */
  padding: 0; /* Ensures no additional padding distorts the shape */
  position: absolute; /* Make the button absolute */
  right: 20px; /* Align it to the right */
  top: 0; /* Align it to the top */
  &:hover {
    background-color: #333; /* Changes color on hover */
  }
`;

const Container = styled.section`
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative; /* Make the container relative for positioning */
  padding-right: 60px; /* Add padding to avoid overlap with button */
`;

const Header = styled.section`
  display: flex;
  flex-direction: row;
  font-weight: bold;
  font-size: ${fontSizes.m};
  align-items: center;
`;

const Answer = styled.section`
  font-size: ${fontSizes.s};
`;

const Divider = styled.section`
  background-color: ${color.accent};
  height: 5px;
  width: 60px;
`;

const disclaimer =
  'This answer has been generated using AI based on resources in the ' +
  'knowledgebase. Generative AI is experimental and may ' +
  'not find the appropriate answer sometimes.';

export default function GeneratedAnswer({
  answer,
  queryInfo,
  regenerateAndBypassCache,
  cacheEnabled,
  setCacheEnabled,
  abortController,
  setAbortController,
  setAnswer,
}: GeneratedAnswerProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [showError, setShowError] = useState(false);

  useEffect(() => {
    setIsGenerating(!!abortController);
  }, [abortController]);

  useEffect(() => {
    // Check if the answer is just whitespace
    if (answer.trim() === '' && !isGenerating) {
      setShowError(true);
    } else {
      setShowError(false);
    }
  }, [answer, isGenerating]);

  const handleAbort = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setAnswer('');
      setIsGenerating(false);
    }
  };

  return (
    <Container>
      <LLMErrorNotification open={showError} />

      <Header>
        Generated Answer
        <Spacer $width="10px" />
        <MoreInfo info={`${disclaimer}`} width="240px" />
      </Header>

      {queryInfo && queryInfo.isDifferent && (
        <div className="text-sm mb-2">
          Showing result for &apos;{queryInfo.cachedQuery}&apos;
          <br />
          <a
            onClick={regenerateAndBypassCache}
            style={{
              cursor: 'pointer',
              color: 'blue',
              textDecoration: 'underline',
            }}
          >
            Search instead for &apos;{queryInfo.userQuery}&apos;
          </a>
        </div>
      )}

      {isGenerating && answer.length === 0 ? (
        <>
          <Spacer $height="20px" />
          <TypingAnimation />
        </>
      ) : (
        <Answer>
          <ReactMarkdown>{answer}</ReactMarkdown>
        </Answer>
      )}

      {isGenerating && (
        <PauseButton onClick={handleAbort}>
          <FontAwesomeIcon icon={faStop} style={{ color: 'white', fontSize: '16px' }} />
        </PauseButton>
      )}

      <Spacer $height="50px" />
      <Divider />
    </Container>
  );
}
