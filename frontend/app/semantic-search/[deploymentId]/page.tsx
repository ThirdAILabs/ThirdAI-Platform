'use client';

import './page.css';
import styled from 'styled-components';
import React, { useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import SearchBar from './components/SearchBar';
import { Pad, Spacer } from './components/Layout';
import ExampleQueries from './components/ExampleQueries';
import GeneratedAnswer from './components/GeneratedAnswer';
import ReferenceList from './components/ReferenceList';
import * as c from './assets/constants';
import LogoImg from './assets/logos/logo.png';
import { duration, fontSizes, padding } from './stylingConstants';
import Teach from './components/Teach';
import { ModelServiceContext } from './Context';
import {
  ModelService,
  PdfInfo,
  ReferenceInfo,
  Source,
  SearchResult,
  PiiEntity,
} from './modelServices';
import InvalidModelMessage from './components/InvalidModelMessage';
import PdfViewer from './components/pdf_viewer/PdfViewer';
import { Chunk } from './components/pdf_viewer/interfaces';
import UpvoteModal from './components/pdf_viewer/UpvoteModal';
import Chat from './components/chat/Chat';
import ChatToggle from './components/chat/ChatToggle';
import { createDeploymentUrl, createTokenModelUrl } from './components/DeploymentURL';
import PillButton from './components/buttons/PillButton';
import { useParams, useSearchParams } from 'next/navigation';
import { CardTitle } from '@/components/ui/card';
import { getWorkflowDetails, fetchCachedGeneration } from '@/lib/backend';

const Frame = styled.section<{ $opacity: string }>`
  position: absolute;
  width: 100%;
  height: 100%;
  overflow-x: visible;
  opacity: ${(props) => props.$opacity};
  transition-duration: ${duration.transition};
`;

const Logo = styled.img`
  position: fixed;
  object-fit: fill;
  height: 50px;
  padding: 10px;

  &:hover {
    cursor: pointer;
  }
`;

const SearchContainer = styled.section<{ $center: boolean }>`
  position: relative; /* Changed from fixed to relative */
  width: 70%;
  left: 10%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: ${(props) => (props.$center ? '100%' : 'fit-content')};
  z-index: 100;
`;

const SearchPrompt = styled.section`
  font-size: ${fontSizes.xl};
`;

const TopRightCorner = styled.section`
  position: fixed;
  display: flex;
  padding: 10px;
  top: 0;
  right: 0;
  z-index: 200;
`;

const PdfViewerWrapper = styled.section`
  display: block;
  position: fixed;
  z-index: 1000;
  width: 100%;
  height: 100%;
  padding: ${padding.card};
  box-sizing: border-box;
  justify-content: center;
`;

const UpvoteModalWrapper = styled.section`
  position: fixed;
  right: 0;
  bottom: 0;
  z-index: 2000;
  margin: 20px;
  width: 450px;
  height: fit-content;
  padding: ${padding.card};
  box-sizing: border-box;
`;

const defaultPrompt =
  'Write an answer that is about 100 words ' +
  'for the query, based on the provided context. ' +
  'If the context provides insufficient information, ' +
  'reply "I cannot answer", and give a reason why. ' +
  'Answer in an unbiased, comprehensive, and scholarly tone. ' +
  'If the query is subjective, provide an opinionated answer ' +
  'in the concluding 1-2 sentences. ' +
  'If the given query is not answerable or is not a question, ' +
  'simply summarize the given context as coherently as possible.';

function App() {
  const [modelService, setModelService] = useState<ModelService | null>(null);
  const [results, setResults] = useState<SearchResult | null>(null);
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [numReferences, setNumReferences] = useState(0);
  const [canSearchMore, setCanSearchMore] = useState(true);
  const [opacity, setOpacity] = useState('0');
  const [failed, setFailed] = useState(false);
  const [pdfInfo, setPdfInfo] = useState<PdfInfo | null>(null);
  const [upvoteQuery, setUpvoteQuery] = useState<string>('');
  const [selectedPdfChunk, setSelectedPdfChunk] = useState<Chunk | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [chatMode, setChatMode] = useState(false);
  const [chatEnabled, setChatEnabled] = useState(false);
  const [checkedIds, setCheckedIds] = useState(new Set<number>());
  const onCheck = (id: number) =>
    setCheckedIds((prev) => {
      const newCheckedIds = new Set(prev.values());
      if (prev.has(id)) {
        newCheckedIds.delete(id);
      } else {
        newCheckedIds.add(id);
      }
      return newCheckedIds;
    });

  const searchParams = useSearchParams();
  const [ifGenerationOn, setIfGenerationOn] = useState(false);
  const [cacheEnabled, setCacheEnabled] = useState(true); // default generation cache is on
  const [ifGuardRailOn, setIfGuardRailOn] = useState(false);
  const [genAiProvider, setGenAiProvider] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);

  const [sentimentClassifierExists, setSentimentClassifierExists] = useState(false);
  const [tokenClassifierExists, setTokenClassifierExists] = useState(false);
  const [sentimentClassifierWorkflowId, setSentimentClassifierWorkflowId] = useState<string | null>(
    null
  );

  // Go to Chat page in case of ChatBot use case
  useEffect(() => {
    const isChatMode = searchParams.get('chatMode') === 'true';
    setChatMode(isChatMode);
  }, []);

  useEffect(() => {
    const receievedWorkflowId = searchParams.get('workflowId');
    const generationOn = searchParams.get('ifGenerationOn') === 'true';
    const provider = searchParams.get('genAiProvider');

    console.log('workflowId', receievedWorkflowId);
    console.log('generationOn', generationOn);
    console.log('genAiProvider', provider);

    setIfGenerationOn(generationOn);
    setGenAiProvider(provider);
    setWorkflowId(receievedWorkflowId);

    const fetchWorkflowDetails = async () => {
      try {
        const details = await getWorkflowDetails(receievedWorkflowId as string);
        console.log('details', details);

        const data = details.data;

        let serviceUrl: string;
        let ragUrl: string | undefined; // Initialize as undefined
        let chatEnabled = false;

        if (data.type === 'enterprise-search') {
          // Enterprise-search logic
          const ragDependency = data.dependencies.find(
            (dep) =>
              dep.model_name.toLowerCase().includes('rag') ||
              dep.model_name.toLowerCase().includes('retrieval')
          );

          serviceUrl = ragDependency
            ? createDeploymentUrl(ragDependency.model_id)
            : createDeploymentUrl('');

          // Only set ragUrl for enterprise-search case
          ragUrl = data.model_id ? createDeploymentUrl(data.model_id) : undefined;

          const nerDependency = data.dependencies.find(
            (dep) =>
              dep.model_name.toLowerCase().includes('pii') ||
              dep.model_name.toLowerCase().includes('ner')
          );

          setIfGuardRailOn(!!nerDependency);
          setTokenClassifierExists(!!nerDependency);

          chatEnabled = true;

          setIfGenerationOn(!!data.llm_provider);
          setGenAiProvider(data.llm_provider || null);
        } else {
          // Non-enterprise-search logic
          serviceUrl = data ? createDeploymentUrl(data.model_id) : createDeploymentUrl('');

          const chatWorkflows = ['rag'];
          chatEnabled = chatWorkflows.includes(data.type);
        }

        // Common logic for both cases
        setChatEnabled(chatEnabled);

        const newModelService = new ModelService(serviceUrl, ragUrl, uuidv4());
        setModelService(newModelService);
        newModelService.sources().then((fetchedSources) => setSources(fetchedSources));
      } catch (error) {
        console.error('Failed to fetch model details:', error);
        // Optionally, handle the error (e.g., show a notification to the user)
      }
    };

    if (receievedWorkflowId) {
      fetchWorkflowDetails();
    }
  }, []);

  // Effect to periodically fetch sources every 3 seconds
  useEffect(() => {
    // Only set up the interval if modelService is available
    if (!modelService) return;

    const fetchSources = async () => {
      try {
        const fetchedSources = await modelService.sources();
        setSources(fetchedSources);
      } catch (error) {
        console.error('Failed to fetch sources:', error);
        // Optionally, handle the error (e.g., show a notification to the user)
      }
    };

    // Fetch immediately before setting up the interval
    fetchSources();

    const intervalId = setInterval(fetchSources, 3000); // 3000ms = 3 seconds

    // Cleanup function to clear the interval when the component unmounts or modelService changes
    return () => clearInterval(intervalId);
  }, [modelService]);

  useEffect(() => {
    if (modelService) {
      setOpacity('100%');
    }
  }, [modelService]);

  const websocketRef = useRef<WebSocket | null>(null);

  async function getResults(
    query: string,
    topK: number,
    queryId?: string
  ): Promise<SearchResult | null> {
    setFailed(false);
    return modelService!
      .predict(/* queryText= */ query, /* topK= */ topK, /* queryId= */ queryId)
      .then((searchResults) => {
        console.log('searchResults', searchResults);
        if (searchResults) {
          setResults(searchResults);
          if (searchResults.references.length < topK) {
            setCanSearchMore(false);
          }
        } else {
          setFailed(true);
        }
        return searchResults;
      })
      .catch((e) => {
        console.log('Prediction error:', e);
        setFailed(true);
        return null;
      });
  }

  const [queryInfo, setQueryInfo] = useState<{
    cachedQuery: string;
    userQuery: string;
    isDifferent: boolean;
  } | null>(null);

  const [abortController, setAbortController] = useState<AbortController | null>(null);

  async function submit(query: string, genaiPrompt: string, bypassCache = false) {
    if (websocketRef.current) {
      websocketRef.current.close();
    }
    setAnswer('');
    setUpvoteQuery(query);
    setResults({ queryId: '', query: '', references: [], pii_entities: null });
    setCheckedIds(new Set<number>());
    setCanSearchMore(true);
    setNumReferences(c.numReferencesFirstLoad);

    if (query.trim().length > 0) {
      // Case 1: Guardrail is ON
      const results = await getResults(
        query,
        c.numReferencesFirstLoad + 1 * c.numReferencesLoadMore
      );

      if (results && ifGenerationOn) {
        if (abortController) {
          abortController.abort();
        }

        console.log('processedQuery:', results.query);
        console.log('piiMap:', results.pii_entities);
        console.log('processedReferences:');
        results.references.forEach((reference) => {
          console.log(reference.content);
        });

        const controller = new AbortController();
        setAbortController(controller); // Store it in state

        modelService!
          .generateAnswer(
            results.query,
            `${genaiPrompt}. [TAG #id] is sensitive information replaced as a placeholder, use them in your response for consistency.`,
            results.references,
            (next) => {
              setAnswer((prev) => {
                // Concatenate previous answer and the new part
                const fullAnswer = prev + next;
                // Return the final processed answer to update the state
                return fullAnswer;
              });
            },
            genAiProvider || undefined, // Convert null to undefined
            workflowId || undefined,
            undefined,
            controller.signal
          )
          .finally(() => {
            // Cleanup after generation completes or is aborted
            setAbortController(null);
          });
      }
    } else {
      setResults(null);
      setAnswer('');
    }
  }

  function regenerateWithSelectedReferences() {
    setAnswer('');
    modelService!.generateAnswer(
      query,
      prompt,
      results!.references.filter((ref) => checkedIds.has(ref.id)),
      (next) => setAnswer((prev) => prev + next),
      genAiProvider || undefined, // Convert null to undefined
      workflowId || undefined
    );
  }

  function chooseExample(example: string) {
    setQuery(example);
    submit(example, prompt);
  }

  function openSource(ref: ReferenceInfo) {
    if (ref.sourceURL.includes('amazonaws.com')) {
      modelService!.openAWSReference(ref);
      return;
    }
    if (!ref.sourceName.toLowerCase().endsWith('.pdf')) {
      modelService!.openReferenceSource(ref);
      return;
    }
    modelService!
      .getPdfInfo(ref)
      .then((pdf) => {
        setPdfInfo(pdf);
        setSelectedPdfChunk(pdf.highlighted);
      })
      .catch((e) => {
        alert('Failed to open PDF. Please try again soon.');
        console.log('Failed to open PDF', e);
      });
  }

  function upvote(refId: number, content: string) {
    modelService!.upvote(
      /* queryId= */ results!.queryId,
      /* queryText= */ results!.query,
      /* referenceId= */ refId,
      /* referenceText= */ content
    );
  }

  function downvote(refId: number, content: string) {
    modelService!.downvote(
      /* queryId= */ results!.queryId,
      /* queryText= */ results!.query,
      /* referenceId= */ refId,
      /* referenceText= */ content
    );
  }

  const moreInBuffer = results && results.references.length > numReferences;
  const showMoreButton = canSearchMore || moreInBuffer;

  function more() {
    const newNumReferences = numReferences + c.numReferencesLoadMore;
    const bufferCoversNextLoad = results!.references.length >= newNumReferences;
    if (canSearchMore && !bufferCoversNextLoad) {
      getResults(query, newNumReferences, results!.queryId).then(() =>
        setNumReferences(newNumReferences)
      );
      return;
    }

    if (moreInBuffer) {
      setNumReferences(newNumReferences);
      return;
    }
  }

  return (
    <ModelServiceContext.Provider value={modelService}>
      {modelService && (
        <Frame $opacity={opacity}>
          <div style={{ height: '100%', width: '100%' }}>
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
            {selectedPdfChunk && (
              <UpvoteModalWrapper>
                <UpvoteModal
                  queryText={upvoteQuery}
                  setQueryText={setUpvoteQuery}
                  upvoteText={selectedPdfChunk.text}
                  onSubmit={() => {
                    modelService.upvote(
                      results!.queryId,
                      upvoteQuery,
                      selectedPdfChunk.id,
                      selectedPdfChunk.text
                    );
                  }}
                />
              </UpvoteModalWrapper>
            )}
            <a href="/">
              <Logo src={LogoImg.src} alt="Logo" />
            </a>
            <TopRightCorner>
              {chatEnabled && (
                <ChatToggle
                  active={chatMode}
                  onClick={() => setChatMode((chatMode) => !chatMode)}
                />
              )}
              <Spacer $width="40px" />
              <Teach />
            </TopRightCorner>
            {chatMode ? (
              <Chat
                tokenClassifierExists={tokenClassifierExists}
                sentimentClassifierExists={sentimentClassifierExists}
                sentimentWorkflowId={sentimentClassifierWorkflowId} // Pass the workflow ID for sentiment classifier
                provider={genAiProvider || 'openai'}
              />
            ) : (
              <>
                <SearchContainer $center={results === null}>
                  {!results && (
                    <Pad $left="5px" $bottom="5px">
                      <CardTitle>How can we help?</CardTitle>
                    </Pad>
                  )}
                  <SearchBar
                    query={query}
                    setQuery={setQuery}
                    onSubmit={submit}
                    sources={sources}
                    setSources={setSources}
                    prompt={prompt}
                    setPrompt={setPrompt}
                    ifGenerationOn={ifGenerationOn}
                    cacheEnabled={cacheEnabled}
                    abortController={abortController}
                    setAbortController={setAbortController}
                    setAnswer={setAnswer}
                  />
                  {failed && (
                    <Pad $top="100px">
                      <InvalidModelMessage />
                    </Pad>
                  )}
                </SearchContainer>
                {results && !failed && (
                  <Pad $top="50px" $bottom="80px" $left="10%" $right="30%">
                    <Pad $left="5px">
                      {ifGenerationOn && (
                        <>
                          <Spacer $height="30px" />
                          <GeneratedAnswer
                            answer={answer}
                            regenerateAndBypassCache={() => {
                              submit(query, prompt, true);
                            }}
                            queryInfo={queryInfo}
                            cacheEnabled={cacheEnabled}
                            setCacheEnabled={setCacheEnabled}
                            abortController={abortController} // Pass abortController here
                            setAbortController={setAbortController} // Pass setAbortController
                            setAnswer={setAnswer} // Pass setAnswer
                          />
                        </>
                      )}
                      <Spacer $height="50px" />
                      {checkedIds.size > 0 && (
                        <PillButton onClick={regenerateWithSelectedReferences}>
                          Regenerate with selected references
                        </PillButton>
                      )}
                      <Spacer $height="50px" />
                      <ReferenceList
                        query={query}
                        references={results.references.slice(0, numReferences)}
                        onOpen={openSource}
                        onUpvote={upvote}
                        onDownvote={downvote}
                        onMore={more}
                        showMoreButton={!!showMoreButton}
                        checkedIds={checkedIds}
                        onCheck={onCheck}
                        modelService={modelService}
                        piiEntities={results.pii_entities}
                      />
                    </Pad>
                  </Pad>
                )}
              </>
            )}
          </div>
        </Frame>
      )}
    </ModelServiceContext.Provider>
  );
}

export default App;
