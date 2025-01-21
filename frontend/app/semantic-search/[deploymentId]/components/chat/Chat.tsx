import React, { useContext, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import styled from 'styled-components';
import { borderRadius, color, duration, fontSizes, padding } from '../../stylingConstants';
import { ModelServiceContext } from '../../Context';
import { ChatMessage, ModelService, ReferenceInfo, PdfInfo } from '../../modelServices';
import { Chunk } from '../pdf_viewer/interfaces';
import PdfViewer from '../pdf_viewer/PdfViewer';
import TypingAnimation from '../TypingAnimation';
import { piiDetect, useSentimentClassification, getWorkflowDetails, deploymentBaseUrl, getSources, getDocumentMetadata } from '@/lib/backend'; // Import for sentiment classification
// Import FontAwesomeIcon and faPause
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faStop } from '@fortawesome/free-solid-svg-icons';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { useSearchParams } from 'next/navigation';

interface MetadataAttribute {
  attribute_name: string;
  value: string | number;
}

interface DocumentMetadata {
  document_id: string;
  document_name: string;
  metadata_attributes: MetadataAttribute[];
}

interface DynamicLabel {
  id: number;
  name: string;
  color: string;
  checked: boolean;
}

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


interface ChatBoxProps {
  message: ChatMessage;
  transformedMessage?: string[][];
  sentiment?: string;
  context?: Reference[];
  modelService: ModelService | null;
  onOpenPdf: (pdfInfo: PdfInfo) => void;
  showFeedback: boolean;
  showReferences?: boolean;
  dynamicLabels: DynamicLabel[]; 
}

function ChatBox({
  message,
  transformedMessage,
  sentiment,
  context,
  modelService,
  onOpenPdf,
  showFeedback,
  showReferences = true,
  dynamicLabels, 
}: ChatBoxProps) {
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
              const label = dynamicLabels.find((label) => label.name === tag);
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

  const searchParams = useSearchParams();
  const workflowId = searchParams.get('workflowId');
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dynamicLabels, setDynamicLabels] = useState<DynamicLabel[]>([]);

  const getColorForAttribute = (attribute: string): string => {
    const colors = ['blue', 'orange', 'green', 'purple', 'red', 'teal'];
    let hash = 0;
    for (let i = 0; i < attribute.length; i++) {
      hash = attribute.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };


  useEffect(() => {
    const fetchMetadata = async () => {
      if (!workflowId) {
        setIsLoading(false);
        return;
      }

      try {
        const workflowDetails = await getWorkflowDetails(workflowId);
        const firstDependency = workflowDetails.data.dependencies?.[0];
        const deploymentUrl = `${deploymentBaseUrl}/${firstDependency.model_id}`;
        
        const sources = await getSources(deploymentUrl);
        const documentsData = await Promise.all(
          sources.map(async (source) => {
            const metadataResponse = await getDocumentMetadata(deploymentUrl, source.source_id);
            return {
              document_id: source.source_id,
              document_name: source.source.split('/').pop() || source.source,
              metadata_attributes: Object.entries(metadataResponse.data).map(([key, value]) => ({
                attribute_name: key,
                value: String(value),
              })),
            };
          })
        );

        // Generate dynamic labels from unique metadata attributes
        const uniqueAttributes = new Set(
          documentsData.flatMap(doc => 
            doc.metadata_attributes.map(attr => attr.attribute_name)
          )
        );

        const newLabels: DynamicLabel[] = Array.from(uniqueAttributes).map((attr, index) => ({
          id: index + 1,
          name: attr.toUpperCase(),
          color: getColorForAttribute(attr),
          checked: true
        }));

        setDynamicLabels(newLabels);
        setDocuments(documentsData);
      } catch (error) {
        console.error('Error fetching metadata:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchMetadata();
  }, [workflowId]);

  const searchMetadataInQuery = (query: string): string[][] => {
    const metadataValues = documents.flatMap(doc => 
      doc.metadata_attributes.map(attr => ({
        value: attr.value,
        tag: attr.attribute_name.toUpperCase()
      }))
    );

    const tokens = query.split(/\s+/);
    let result: string[][] = [];
    let currentPhrase = '';
    let currentTag = '';

    tokens.forEach(token => {
      const match = metadataValues.find(mv => mv.value === token);
      if (match) {
        if (currentPhrase) result.push([currentPhrase.trim(), currentTag]);
        result.push([token, match.tag]);
        currentPhrase = '';
        currentTag = '';
      } else {
        if (!currentTag) {
          currentPhrase = currentPhrase ? `${currentPhrase} ${token}` : token;
        } else {
          result.push([currentPhrase.trim(), currentTag]);
          currentPhrase = token;
          currentTag = '';
        }
      }
    });

    if (currentPhrase) result.push([currentPhrase.trim(), currentTag]);
    return result;
  };

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
      if (!textInput.trim() || isLoading) return;

      // Abort existing generation if any
      if (abortController) {
        abortController.abort();
        setAiLoading(false);
      }

      const controller = new AbortController();
      setAbortController(controller);

      const lastTextInput = textInput;
      const currentIndex = chatHistory.length;
      const aiIndex = chatHistory.length + 1;

      setTextInput('');
      setAiLoading(true);

      const humanMessage: ChatMessage = {
        sender: 'human',
        content: lastTextInput,
      };
      const newHistory = [...chatHistory, humanMessage];
      setChatHistory(newHistory);

      // Handle sentiment if enabled
      if (sentimentWorkflowId) {
        classifySentiment(lastTextInput, currentIndex);
      }

      responseBuffer.current = '';
      contextReceived.current = false;
      isCollectingContext.current = false;
      contextBuffer.current = '';

      try {
        // Search for metadata in query
        const transformed = searchMetadataInQuery(lastTextInput);
        console.log('transformed', transformed)

        setTransformedMessages((prev) => ({
          ...prev,
          [currentIndex]: transformed,
        }));

        // Process all metadata constraints
        const newConstraints: SearchConstraints = {};
        transformed.forEach(([text, tag]) => {
          // Check if tag exists in dynamicLabels
          if (dynamicLabels.some(label => label.name === tag)) {
            newConstraints[tag] = {
              constraint_type: 'EqualTo',
              value: text.trim(),
            };
          }
        });

        if (Object.keys(newConstraints).length > 0) {
          setPersistentConstraints(newConstraints);
        }

        // Initialize AI message
        setChatHistory((prev) => [...prev, { sender: 'AI', content: '' }]);

        // Start chat with streaming
        await modelService?.chat(
          lastTextInput,
          provider,
          Object.keys(newConstraints).length > 0 ? newConstraints : persistentConstraints,
          (newData: string) => {
            if (newData.startsWith('context:') || isCollectingContext.current) {
              // Handle context streaming
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
              }
            } else if (!isCollectingContext.current) {
              // Handle message streaming
              responseBuffer.current += newData;
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
            // Final callback
            const finalContent = responseBuffer.current;
            setChatHistory((prev) => {
              const updatedHistory = [...prev];
              const lastMessage = updatedHistory[updatedHistory.length - 1];
              if (lastMessage?.sender === 'AI') {
                return [...updatedHistory.slice(0, -1), { ...lastMessage, content: finalContent }];
              }
              return [...updatedHistory, { sender: 'AI', content: finalContent }];
            });
  
            setAiLoading(false);
            setAbortController(null);
            responseBuffer.current = finalContent;
            contextBuffer.current = '';
            isCollectingContext.current = false;
          },
          controller.signal
        );
      } catch (error) {
        console.error('Chat error:', error);
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
                dynamicLabels = {dynamicLabels}
                key={i}
                modelService={modelService}
                message={message}
                transformedMessage={true ? transformedMessages[i] : undefined}
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
            dynamicLabels={dynamicLabels}
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
