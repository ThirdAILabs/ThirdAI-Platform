import React, { useContext, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import styled from 'styled-components';
import { borderRadius, color, duration, fontSizes, padding } from '../../stylingConstants';
import { ModelServiceContext } from '../../Context';
import { ChatMessage, ModelService, ReferenceInfo, PdfInfo } from '../../modelServices';
import { Chunk } from '../pdf_viewer/interfaces';
import PdfViewer from '../pdf_viewer/PdfViewer';
import TypingAnimation from '../TypingAnimation';
import { piiDetect, useSentimentClassification } from '@/lib/backend'; // Import for sentiment classification
// Import FontAwesomeIcon and faPause
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faStop } from '@fortawesome/free-solid-svg-icons';
import { ThumbsUp, ThumbsDown } from 'lucide-react';

const PdfViewerWrapper = styled.section`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  width: 100%;
  height: 100%;
  padding: ${padding.card};
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  justify-content: center;
  align-items: center;
`;

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
    name: 'BRAND',
    color: 'blue',
    amount: '217,323',
    checked: true,
    description:
      'The format of a US phone number is (XXX) XXX-XXXX, where "X" represents a digit from 0 to 9. It consists of a three-digit area code, followed by a three-digit exchange code, and a four-digit line number.',
  },
  {
    id: 2,
    name: 'MODEL_NUMBER',
    color: 'orange',
    amount: '8,979',
    checked: true,
    description:
      'The format of a US Social Security Number (SSN) is XXX-XX-XXXX, where "X" represents a digit from 0 to 9. It consists of three parts: area, group, and serial numbers.',
  },
];

// ChatBox component to display human/AI message with sentiment
const sentimentColor = (sentiment: string) => {
  switch (sentiment) {
    case 'positive':
      return 'green';
    case 'neutral':
      return 'orange';
    case 'negative':
      return 'red';
    default:
      return '#888';
  }
};

interface VoteButtonProps {
  onClick: (e: React.MouseEvent) => void;
  icon: React.ElementType;
  active?: boolean;
}

const VoteButton: React.FC<VoteButtonProps> = ({ onClick, icon: Icon, active = false }) => (
  <button
    onClick={onClick}
    className={`p-2 rounded-full transition-colors flex items-center justify-center w-8 h-8 ${
      active ? 'bg-[#3B52DD] text-white' : 'text-gray-500 hover:bg-gray-100'
    }`}
  >
    <Icon size={16} />
  </button>
);

interface Reference {
  chunk_id: number;
  query: string;
  sourceURL: string;
  sourceName: string;
  content: string;
  metadata: any;
}

interface ReferenceItemProps {
  reference: Reference;
  query: string;
  onVote: (refId: number, content: string, voteType: 'up' | 'down') => void;
  onReferenceClick: (reference: Reference) => void;
}

const ReferenceItem: React.FC<ReferenceItemProps> = ({
  reference,
  query,
  onVote,
  onReferenceClick,
}) => {
  const [activeVote, setActiveVote] = useState<'up' | 'down' | null>(null);

  const handleVote = (voteType: 'up' | 'down') => (e: React.MouseEvent) => {
    e.stopPropagation();
    if (activeVote !== voteType) {
      setActiveVote(voteType);
      onVote(reference.chunk_id, reference.content, voteType);
    }
  };

  return (
    <div className="bg-gray-50 rounded-lg p-3 relative">
      <div className="flex justify-between items-start">
        <button
          onClick={() => onReferenceClick(reference)}
          className="text-blue-600 hover:text-blue-800 font-medium mb-1 transition-colors"
        >
          {reference.sourceName}
        </button>
        <div className="flex items-center gap-1">
          <VoteButton onClick={handleVote('up')} icon={ThumbsUp} active={activeVote === 'up'} />
          <VoteButton
            onClick={handleVote('down')}
            icon={ThumbsDown}
            active={activeVote === 'down'}
          />
        </div>
      </div>
      <div className="text-gray-700 text-sm mt-1">
        {reference.content.length > 150
          ? `${reference.content.substring(0, 150)}...`
          : reference.content}
      </div>
    </div>
  );
};

function ChatBox({
  message,
  transformedMessage,
  sentiment,
  context,
  modelService,
  onOpenPdf,
  showFeedback,
  showReferences = true,
}: {
  message: ChatMessage;
  transformedMessage?: string[][];
  sentiment?: string;
  context?: Reference[];
  modelService: ModelService | null;
  onOpenPdf: (pdfInfo: PdfInfo) => void;
  showFeedback: boolean;
  showReferences?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const references = context || message.references || [];

  const handleReferenceClick = async (chunkInfo: any) => {
    if (!modelService) return;

    const ref: ReferenceInfo = {
      id: chunkInfo.chunk_id,
      sourceURL: chunkInfo.sourceURL,
      sourceName: chunkInfo.sourceName,
      content: chunkInfo.content,
      metadata: chunkInfo.metadata,
    };

    try {
      if (!ref.sourceURL.toLowerCase().endsWith('.pdf')) {
        modelService.openReferenceSource(ref);
        return;
      }

      const pdfInfo = await modelService.getPdfInfo(ref);
      onOpenPdf(pdfInfo);
    } catch (error) {
      console.error('Failed to open reference:', error);
      alert('Failed to open reference. Please try again.');
    }
  };

  const handleUpvote = () => {
    modelService?.recordGeneratedResponseFeedback(true);
  };
  const handleDownvote = () => {
    modelService?.recordGeneratedResponseFeedback(false);
  };

  // Check if this is the welcome message
  const isWelcomeMessage =
    message.sender === 'AI' && message.content.startsWith("Welcome! I'm here to assist you");

  return (
    <ChatBoxContainer>
      <ChatBoxSender>{message.sender === 'human' ? '👋 You' : '🤖 AI'}</ChatBoxSender>
      <ChatBoxContent>
        <div>
          {transformedMessage && transformedMessage.length > 0 ? (
            transformedMessage.map(([sentence, tag], index) => {
              const label = labels.find((label) => label.name === tag);
              return (
                <span key={index} style={{ color: label?.checked ? label.color : 'inherit' }}>
                  {sentence} {label?.checked && `(${tag}) `}
                </span>
              );
            })
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
          {showFeedback && message.sender === 'AI' && !isWelcomeMessage && (
            <div className="flex mt-4 justify-center">
              <div className="flex items-center justify-center space-x-4 px-4 bg-gray-50 border rounded-xl w-fit">
                <p className="text-sm font-medium text-gray-700">Was this helpful?</p>
                <button
                  onClick={handleUpvote}
                  className="flex items-center justify-center w-8 h-8 text-gray-800 rounded-full hover:bg-gray-200 focus:bg-blue-700"
                >
                  <ThumbsUp className="w-4 h-4" />
                </button>
                <button
                  onClick={handleDownvote}
                  className="flex items-center justify-center w-8 h-8 text-gray-800 rounded-full hover:bg-gray-200 focus:bg-blue-700"
                >
                  <ThumbsDown className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
          {message.sender === 'human' && sentiment && (
            <span
              style={{
                fontSize: '0.85rem',
                marginLeft: '8px',
                color: sentimentColor(sentiment),
                whiteSpace: 'nowrap',
              }}
            >
              [sentiment: {sentiment}]
            </span>
          )}
        </div>

        {showReferences && references.length > 0 && message.sender === 'AI' && (
          <div className="mt-2">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center text-sm text-gray-600 hover:text-gray-800"
            >
              <span
                className={`transform transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
              >
                ▶
              </span>
              <span className="ml-1 font-medium">References ({references.length})</span>
            </button>
            {isExpanded && (
              <div className="space-y-2 mt-2">
                {references.map((ref, i) => (
                  <ReferenceItem
                    key={i}
                    reference={ref}
                    query={ref.query}
                    onVote={(refId, content, voteType) => {
                      if (voteType === 'up') {
                        modelService?.upvote('null', ref.query, refId, content);
                      } else {
                        modelService?.downvote('null', ref.query, refId, content);
                      }
                    }}
                    onReferenceClick={handleReferenceClick}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </ChatBoxContent>
    </ChatBoxContainer>
  );
}

// AI typing animation while the response is being processed
function AILoadingChatBox() {
  return <TypingAnimation />;
}

export interface SearchConstraint {
  constraint_type: 'EqualTo';
  value: string;
}

// Using Record directly instead of a custom interface
type SearchConstraints = Record<string, SearchConstraint>;

export default function Chat({
  piiWorkflowId, // Workflow ID for pii detection
  sentimentWorkflowId, // Workflow ID for sentiment classification
  provider,
}: {
  piiWorkflowId: string | null;
  sentimentWorkflowId: string | null;
  provider: string;
}) {
  const modelService = useContext<ModelService | null>(ModelServiceContext);
  const { predictSentiment } = useSentimentClassification(sentimentWorkflowId); // Use new hook for sentiment classification

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [textInput, setTextInput] = useState('');
  const [transformedMessages, setTransformedMessages] = useState<Record<number, string[][]>>({});
  const [aiLoading, setAiLoading] = useState(false);
  const [persistentConstraints, setPersistentConstraints] = useState<SearchConstraints>({});
  const scrollableAreaRef = useRef<HTMLElement | null>(null);
  const responseBuffer = useRef<string>('');
  const contextReceived = useRef<boolean>(false);
  const [contextData, setContextData] = useState<Record<number, any>>({});
  const contextBuffer = useRef<string>('');
  const isCollectingContext = useRef<boolean>(false);

  useEffect(() => {
    if (modelService && provider) {
      modelService
        .setChat(provider)
        .then(() => {
          modelService.getChatHistory(provider).then((history) => {
            setChatHistory(history);
            // Also set up the context data from the saved references
            const contextDataFromHistory: Record<number, Reference[]> = {};
            history.forEach((message, index) => {
              if (message.references?.length) {
                contextDataFromHistory[index] = message.references;
              }
            });
            setContextData(contextDataFromHistory);
          });
        })
        .catch((e) => {
          console.error('Failed to update chat settings:', e);
        });
    }
  }, [modelService, provider]);

  const performPIIDetection = (messageContent: string): Promise<string[][]> => {
    if (!piiWorkflowId) {
      return Promise.resolve([]);
    }

    return piiDetect(messageContent, piiWorkflowId)
      .then((result) => {
        const { tokens, predicted_tags } = result.data.prediction_results;

        let transformed: string[][] = [];
        let currentSentence = '';
        let currentTag = '';

        console.log('tokens', tokens);
        console.log('predicted_tags', predicted_tags);

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
    if (!sentimentWorkflowId) {
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
      const currentIndex = chatHistory.length;
      const aiIndex = chatHistory.length + 1;

      // Clear input and set loading state
      setTextInput('');
      setAiLoading(true);

      // Add human message
      const humanMessage: ChatMessage = {
        sender: 'human',
        content: lastTextInput,
      };
      const newHistory = [...chatHistory, humanMessage];
      setChatHistory(newHistory);

      // Handle sentiment classification
      if (sentimentWorkflowId) {
        classifySentiment(lastTextInput, currentIndex);
      }

      // Reset buffers and state
      responseBuffer.current = '';
      contextReceived.current = false;
      isCollectingContext.current = false;
      contextBuffer.current = '';

      try {
        // Handle PII detection
        if (piiWorkflowId) {
          const humanTransformed = await performPIIDetection(lastTextInput);
          setTransformedMessages((prev) => ({
            ...prev,
            [currentIndex]: humanTransformed,
          }));
        }

        // Process constraints
        const detectedPII = await performPIIDetection(lastTextInput);
        const newConstraints: SearchConstraints = {};
        detectedPII.forEach(([text, tag]) => {
          if (tag === 'BRAND' || tag === 'MODEL_NUMBER') {
            newConstraints[tag] = {
              constraint_type: 'EqualTo',
              value: text.trim(),
            };
          }
        });

        if (Object.keys(newConstraints).length > 0) {
          setPersistentConstraints(newConstraints);
        }

        // Initialize AI message in chat history
        setChatHistory((prev) => [...prev, { sender: 'AI', content: '' }]);

        // Start chat with streaming
        await modelService?.chat(
          lastTextInput,
          provider,
          Object.keys(newConstraints).length > 0 ? newConstraints : persistentConstraints,
          (newData: string) => {
            if (newData.startsWith('context:') || isCollectingContext.current) {
              // Handle context streaming
              try {
                if (newData.startsWith('context:')) {
                  isCollectingContext.current = true;
                  contextBuffer.current = newData.substring(9);
                } else {
                  contextBuffer.current += newData;
                }

                try {
                  const contextJson = JSON.parse(contextBuffer.current);
                  setContextData((prev) => ({
                    ...prev,
                    [aiIndex]: contextJson,
                  }));
                  isCollectingContext.current = false;
                  contextBuffer.current = '';
                } catch {
                  // Continue collecting context if JSON is incomplete
                  return;
                }
              } catch (e) {
                console.error('Error handling context:', e);
              }
            } else if (!isCollectingContext.current) {
              // Handle message streaming
              responseBuffer.current += newData;

              // Update chat history with new content
              setChatHistory((prev) => {
                const updatedHistory = [...prev];
                const lastMessage = updatedHistory[updatedHistory.length - 1];

                if (lastMessage?.sender === 'AI') {
                  return [
                    ...updatedHistory.slice(0, -1),
                    { ...lastMessage, content: responseBuffer.current },
                  ];
                }
                return updatedHistory;
              });
            }
          },
          () => {
            // Final callback - ensure message persists
            const finalContent = responseBuffer.current;

            setChatHistory((prev) => {
              const updatedHistory = [...prev];
              const lastMessage = updatedHistory[updatedHistory.length - 1];

              if (lastMessage?.sender === 'AI') {
                return [...updatedHistory.slice(0, -1), { ...lastMessage, content: finalContent }];
              }
              // If no AI message exists, add it
              return [...updatedHistory, { sender: 'AI', content: finalContent }];
            });

            // Reset state
            setAiLoading(false);
            setAbortController(null);
            responseBuffer.current = finalContent; // Keep the content in buffer
            contextBuffer.current = '';
            isCollectingContext.current = false;
          },
          controller.signal
        );
      } catch (error) {
        console.error('Chat error:', error);
        // Handle error state
        setChatHistory((prev) => {
          const updatedHistory = [...prev];
          const lastMessage = updatedHistory[updatedHistory.length - 1];

          if (lastMessage?.sender === 'AI') {
            return [
              ...updatedHistory.slice(0, -1),
              {
                ...lastMessage,
                content: responseBuffer.current || 'An error occurred during the response.',
              },
            ];
          }
          return updatedHistory;
        });

        setAiLoading(false);
        setAbortController(null);
      }
    }
  };

  const [pdfInfo, setPdfInfo] = useState<PdfInfo | null>(null);
  const [selectedPdfChunk, setSelectedPdfChunk] = useState<Chunk | null>(null);

  const handleOpenPdf = (info: PdfInfo) => {
    setPdfInfo(info);
    setSelectedPdfChunk(info.highlighted);
  };

  return (
    <ChatContainer>
      {pdfInfo && (
        <PdfViewerWrapper>
          <PdfViewer
            name={pdfInfo.filename}
            src={pdfInfo.source}
            chunks={pdfInfo.docChunks}
            initialChunk={pdfInfo.highlighted}
            onSelect={setSelectedPdfChunk}
            onClose={() => {
              setSelectedPdfChunk(null);
              setPdfInfo(null);
            }}
          />
        </PdfViewerWrapper>
      )}
      <ScrollableArea ref={scrollableAreaRef}>
        {chatHistory && chatHistory.length ? (
          <AllChatBoxes>
            {chatHistory.map((message, i) => (
              <ChatBox
                key={i}
                modelService={modelService}
                message={message}
                transformedMessage={piiWorkflowId ? transformedMessages[i] : undefined}
                sentiment={sentiments[i]}
                context={contextData[i]}
                onOpenPdf={handleOpenPdf}
                showFeedback={!aiLoading}
                showReferences={i < chatHistory.length - 1 || !aiLoading} // Show references for all messages except the last one during generation
              />
            ))}
            {aiLoading && (
              <AILoadingWrapper>
                <AILoadingChatBox />
              </AILoadingWrapper>
            )}
          </AllChatBoxes>
        ) : (
          <ChatBox
            message={{
              sender: 'AI',
              content:
                "Welcome! I'm here to assist you with any questions or issues related to air-conditioners.\n\nFeel free to share the BRAND and MODEL_NUMBER of your air-conditioner if you have it handy. Don't worry if you don't. Just tell me what you need, and I'll do my best to answer!",
            }}
            modelService={modelService}
            onOpenPdf={handleOpenPdf}
            showFeedback={!aiLoading}
          />
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
