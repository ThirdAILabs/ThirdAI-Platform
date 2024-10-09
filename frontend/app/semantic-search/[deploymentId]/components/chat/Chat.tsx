import React, { useContext, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import styled from 'styled-components';
import { borderRadius, color, duration, fontSizes, padding } from '../../stylingConstants';
import { ModelServiceContext } from '../../Context';
import { ChatMessage, ModelService } from '../../modelServices';
import TypingAnimation from '../TypingAnimation';
import { useTextClassificationEndpoints, useSentimentClassification } from '@/lib/backend'; // Import for sentiment classification
// Import FontAwesomeIcon and faPause
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faStop } from '@fortawesome/free-solid-svg-icons';

// Styled component for the pause button
const PauseButton = styled.button`
  width: 40px;
  height: 40px;
  background-color: black;
  border: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;
  box-sizing: border-box;
  padding: 0;

  &:hover {
    background-color: #333;
  }
`;

const ChatBarContainer = styled.div`
  display: flex;
  align-items: center;
  width: 100%; // Ensure it takes the full width
  margin: 10px 0 50px 0%; // Adjust margins as needed
`;

// Styled components for chat UI
const ChatContainer = styled.section`
  position: fixed;
  width: 60%;
  left: 10%;
  display: flex;
  flex-direction: column;
  justify-content: end;
  z-index: 100;
  height: 100%;
  font-family: Helvetica, Arial, sans-serif;
`;

const ChatBoxContainer = styled.section`
  padding: 15px 15px 0 15px;
`;

const ChatBoxSender = styled.section`
  font-size: ${fontSizes.l};
  font-weight: bold;
  color: ${color.accent};
`;

const ChatBoxContent = styled.section`
  font-size: ${fontSizes.m};
  padding-bottom: 15px;
`;

const TypingAnimationContainer = styled.section`
  padding: ${padding.card} 0 7px 0;
`;

const ChatBar = styled.textarea`
  background-color: ${color.textInput};
  font-size: ${fontSizes.m};
  padding: 20px;
  border-radius: ${borderRadius.textInput};
  outline: none;
  border: none;
  transition-duration: ${duration.transition};
  height: ${fontSizes.xl};
  resize: none;
  font-family: Helvetica, Arial, sans-serif;
  flex: 1; // Add this line to make it expand
  margin-right: 10px; // Add some space between the ChatBar and the PauseButton

  &:focus {
    height: 100px;
    transition-duration: ${duration.transition};
  }
`;

const ScrollableArea = styled.section`
  overflow-y: scroll;
  display: flex;
  flex-direction: column-reverse;
  height: 80%;
`;

const AILoadingWrapper = styled.div`
  margin-left: 10px;
`;

const AllChatBoxes = styled.section``;

const Placeholder = styled.section`
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  font-size: ${fontSizes.l};
  height: 80%;
`;

const labels = [
  {
    id: 1,
    name: 'PHONENUMBER',
    color: 'blue',
    amount: '217,323',
    checked: true,
    description:
      'The format of a US phone number is (XXX) XXX-XXXX, where "X" represents a digit from 0 to 9. It consists of a three-digit area code, followed by a three-digit exchange code, and a four-digit line number.',
  },
  {
    id: 2,
    name: 'SSN',
    color: 'orange',
    amount: '8,979',
    checked: true,
    description:
      'The format of a US Social Security Number (SSN) is XXX-XX-XXXX, where "X" represents a digit from 0 to 9. It consists of three parts: area, group, and serial numbers.',
  },
  {
    id: 3,
    name: 'CREDITCARDNUMBER',
    color: 'red',
    amount: '13,272',
    checked: true,
    description:
      'A US credit card number is a 16-digit number typically formatted as XXXX XXXX XXXX XXXX, where "X" represents a digit from 0 to 9. It includes the Issuer Identifier, account number, and a check digit.',
  },
  {
    id: 4,
    name: 'LOCATION',
    color: 'green',
    amount: '2,576,904',
    checked: true,
    description: `A US address format includes the recipient's name, street address (number and name), city, state abbreviation, and ZIP code, for example: John Doe 123 Main St Springfield, IL 62701`,
  },
  {
    id: 5,
    name: 'NAME',
    color: 'purple',
    amount: '1,758,131',
    checked: true,
    description: `An English name format typically consists of a first name, middle name(s), and last name (surname), for example: John Michael Smith. Titles and suffixes, like Mr. or Jr., may also be included.`,
  },
];

// ChatBox component to display human/AI message with sentiment
function ChatBox({
  message,
  transformedMessage,
  sentiment,
}: {
  message: ChatMessage;
  transformedMessage?: string[][];
  sentiment?: string;
}) {
  const sentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': // Positive sentiment
        return 'green';
      case 'neutral': // Neutral sentiment
        return 'orange';
      case 'negative': // Negative sentiment
        return 'red';
      default:
        return '#888'; // Default gray for unknown sentiment
    }
  };

  console.log('sentiment', sentiment);

  return (
    <ChatBoxContainer>
      <ChatBoxSender>{message.sender === 'human' ? '👋 You' : '🤖 AI'}</ChatBoxSender>
      <ChatBoxContent style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ flexGrow: 1 }}>
          {
            transformedMessage && transformedMessage.length > 0 ? (
              transformedMessage.map(([sentence, tag], index) => {
                const label = labels.find((label) => label.name === tag);
                return (
                  <span
                    key={index}
                    style={{
                      color: label?.checked ? label.color : 'inherit',
                    }}
                  >
                    {sentence} {label?.checked && `(${tag}) `}
                  </span>
                );
              })
            ) : (
              <ReactMarkdown>{message.content}</ReactMarkdown>
            ) // Render without PII highlighting if no transformation is available
          }
        </div>

        {/* Display sentiment text for human messages */}
        {message.sender === 'human' && sentiment && (
          <span
            style={{
              fontSize: '0.85rem',
              marginLeft: '8px',
              color: sentimentColor(sentiment), // Apply color based on sentiment
              whiteSpace: 'nowrap',
            }}
          >
            [sentiment: {sentiment}] {/* Directly displaying the sentiment label */}
          </span>
        )}
      </ChatBoxContent>
    </ChatBoxContainer>
  );
}

// AI typing animation while the response is being processed
function AILoadingChatBox() {
  return <TypingAnimation />;
}

export default function Chat({
  tokenClassifierExists,
  sentimentClassifierExists, // Indicates if sentiment classification model exists
  sentimentWorkflowId, // Workflow ID for sentiment classification
  provider,
}: {
  tokenClassifierExists: boolean;
  sentimentClassifierExists: boolean;
  sentimentWorkflowId: string | null;
  provider: string;
}) {
  const modelService = useContext<ModelService | null>(ModelServiceContext);
  const { predictSentiment } = useSentimentClassification(sentimentWorkflowId); // Use new hook for sentiment classification

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [textInput, setTextInput] = useState('');
  const [transformedMessages, setTransformedMessages] = useState<Record<number, string[][]>>({});
  const [aiLoading, setAiLoading] = useState(false);
  const scrollableAreaRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (modelService && provider) {
      // Set the chat settings based on the provider
      modelService
        .setChat(provider)
        .then(() => {
          // After setting chat settings, fetch chat history
          modelService.getChatHistory(provider).then(setChatHistory);
        })
        .catch((e) => {
          console.error('Failed to update chat settings:', e);
        });
    }
  }, [modelService, provider]);

  const performPIIDetection = (messageContent: string): Promise<string[][]> => {
    if (!modelService) {
      return Promise.resolve([]);
    }

    return modelService
      .piiDetect(messageContent)
      .then((result) => {
        const { tokens, predicted_tags } = result;
        let transformed: string[][] = [];
        let currentSentence = '';
        let currentTag = '';

        for (let i = 0; i < tokens.length; i++) {
          const word = tokens[i];
          const tag = predicted_tags[i] && predicted_tags[i][0];

          if (tag !== currentTag) {
            if (currentSentence) {
              transformed.push([currentSentence.trim(), currentTag]);
            }
            currentSentence = word;
            currentTag = tag;
          } else {
            currentSentence += ` ${word}`;
          }
        }

        if (currentSentence) {
          transformed.push([currentSentence.trim(), currentTag]);
        }

        return transformed;
      })
      .catch((error) => {
        console.error('Error detecting PII:', error);
        return [];
      });
  };

  const [sentiments, setSentiments] = useState<Record<number, string>>({}); // Store sentiment for human messages

  // Function to classify sentiment and store the highest sentiment score
  const classifySentiment = async (messageContent: string, messageIndex: number) => {
    if (!sentimentClassifierExists || !sentimentWorkflowId) {
      return;
    }

    try {
      const result = await predictSentiment(messageContent);
      const predictions = result.predicted_classes; // Array of [sentiment, score]
      console.log('Sentiment Prediction:', result);

      // Find the sentiment with the highest score
      const [maxSentiment, maxScore] = predictions.reduce((prev, current) => {
        return current[1] > prev[1] ? current : prev;
      });

      // Special case: if sentiment is 'positive', 'neutral', or 'negative', apply the 0.7 threshold
      let finalSentiment = maxSentiment;
      if (['positive', 'negative', 'neutral'].includes(maxSentiment)) {
        if ((maxSentiment === 'positive' || maxSentiment === 'negative') && maxScore < 0.7) {
          finalSentiment = 'neutral'; // Override to 'neutral' if score is below 0.7
        }
      }

      // For any other sentiment labels (not positive/negative/neutral), use the highest score directly
      setSentiments((prev) => ({
        ...prev,
        [messageIndex]: finalSentiment, // Save the final sentiment for this message
      }));
    } catch (error) {
      console.error('Error classifying sentiment:', error);
    }
  };

  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const handleEnterPress = async (e: any) => {
    if (e.keyCode === 13 && e.shiftKey === false) {
      e.preventDefault();
      if (!textInput.trim()) return;

      // If a generation is already in progress, abort it
      if (abortController) {
        abortController.abort();
        setAiLoading(false);
      }

      const controller = new AbortController();
      setAbortController(controller);

      const lastTextInput = textInput;
      const lastChatHistory = chatHistory;
      const currentIndex = chatHistory.length;

      setAiLoading(true);
      setChatHistory((history) => [...history, { sender: 'human', content: lastTextInput }]);
      setTextInput('');

      // Trigger sentiment classification if classifier exists
      if (sentimentClassifierExists) {
        classifySentiment(lastTextInput, currentIndex);
      }

      // Perform PII detection on the human's message
      if (tokenClassifierExists) {
        const humanTransformed = await performPIIDetection(lastTextInput);
        setTransformedMessages((prev) => ({
          ...prev,
          [currentIndex]: humanTransformed,
        }));
      }

      try {
        let aiResponse = '';
        const aiIndex = chatHistory.length + 1;

        await modelService?.chat(
          lastTextInput,
          provider,
          (newWord: string) => {
            aiResponse += newWord;
            setChatHistory((history) => {
              const newHistory = [...history];
              if (newHistory[newHistory.length - 1].sender === 'AI') {
                newHistory[newHistory.length - 1].content = aiResponse;
              } else {
                newHistory.push({ sender: 'AI', content: aiResponse });
              }
              return newHistory;
            });
          },
          async (finalResponse: string) => {
            if (tokenClassifierExists) {
              const aiTransformed = await performPIIDetection(finalResponse);
              setTransformedMessages((prev) => ({
                ...prev,
                [aiIndex]: aiTransformed,
              }));
            }
            setAiLoading(false);
            setAbortController(null);
          },
          controller.signal
        );
      } catch (error) {
        // Type guard for Error objects
        if (error instanceof Error) {
          if (error.name === 'AbortError') {
            console.log('Chat was aborted');
            // Don't reset the chat history or text input for aborted requests
          } else {
            console.error('Error in chat:', error);
            alert('Failed to send chat. Please try again.');
            setChatHistory(lastChatHistory);
            setTextInput(lastTextInput);
          }
        } else {
          console.error('An unknown error occurred:', error);
          alert('Failed to send chat. Please try again.');
          setChatHistory(lastChatHistory);
          setTextInput(lastTextInput);
        }
      } finally {
        setAiLoading(false);
        setAbortController(null);
      }
    }
  };

  return (
    <ChatContainer>
      <ScrollableArea ref={scrollableAreaRef}>
        {chatHistory && chatHistory.length ? (
          <AllChatBoxes>
            {chatHistory.map((message, i) => (
              <ChatBox
                key={i}
                message={message}
                transformedMessage={tokenClassifierExists ? transformedMessages[i] : undefined} // Pass PII-transformed message for human and AI
                sentiment={sentiments[i]} // Pass sentiment for human message
              />
            ))}
            {aiLoading && (
              <AILoadingWrapper>
                <AILoadingChatBox />
              </AILoadingWrapper>
            )}
          </AllChatBoxes>
        ) : (
          <Placeholder> Ask anything to start chatting! </Placeholder>
        )}
      </ScrollableArea>
      <ChatBarContainer>
        <ChatBar
          placeholder="Ask anything..."
          onKeyDown={handleEnterPress}
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
        />
        {abortController && aiLoading && (
          <PauseButton
            onClick={() => {
              abortController.abort();
              setAbortController(null);
              setAiLoading(false);
            }}
          >
            <FontAwesomeIcon icon={faStop} style={{ color: 'white', fontSize: '16px' }} />
          </PauseButton>
        )}
      </ChatBarContainer>
    </ChatContainer>
  );
}
