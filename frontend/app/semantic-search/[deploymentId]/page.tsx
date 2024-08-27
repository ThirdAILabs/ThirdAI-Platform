"use client"

import "./page.css";
import styled from "styled-components";
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import SearchBar from "./components/SearchBar";
import { Pad, Spacer } from "./components/Layout";
import ExampleQueries from "./components/ExampleQueries";
import GeneratedAnswer from "./components/GeneratedAnswer";
import ReferenceList from "./components/ReferenceList";
import * as c from "./assets/constants";
import LogoImg from "./assets/logos/logo.png";
import { duration, fontSizes, padding } from "./stylingConstants";
import Teach from "./components/Teach";
import { ModelServiceContext } from "./Context";
import {
    ModelService,
    PdfInfo,
    ReferenceInfo,
    Source,
} from "./modelServices";
import InvalidModelMessage from "./components/InvalidModelMessage";
import PdfViewer from "./components/pdf_viewer/PdfViewer";
import { Chunk } from "./components/pdf_viewer/interfaces";
import UpvoteModal from "./components/pdf_viewer/UpvoteModal";
import Chat from "./components/chat/Chat";
import ChatToggle from "./components/chat/ChatToggle";
import { createDeploymentUrl, createTokenModelUrl } from "./components/DeploymentURL";
import PillButton from "./components/buttons/PillButton";
import { useParams, useSearchParams } from "next/navigation";
import { CardTitle } from "@/components/ui/card";
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
    position: fixed;
    width: 70%;
    left: 10%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: ${(props) => (props.$center ? "100%" : "fit-content")};
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

interface SearchResult {
    queryId: string;
    query: string;
    references: ReferenceInfo[];
}

const defaultPrompt =
    "Write an answer that is about 100 words " +
    "for the query, based on the provided context. " +
    "If the context provides insufficient information, " +
    'reply "I cannot answer", and give a reason why. ' +
    "Answer in an unbiased, comprehensive, and scholarly tone. " +
    "If the query is subjective, provide an opinionated answer " +
    "in the concluding 1-2 sentences. " +
    "If the given query is not answerable or is not a question, " +
    "simply summarize the given context as coherently as possible.";

function App() {
    const [modelService, setModelService] = useState<ModelService | null>(null);
    const [results, setResults] = useState<SearchResult | null>(null);
    const [prompt, setPrompt] = useState(defaultPrompt);
    const [query, setQuery] = useState("");
    const [answer, setAnswer] = useState("");
    const [numReferences, setNumReferences] = useState(0);
    const [canSearchMore, setCanSearchMore] = useState(true);
    const [opacity, setOpacity] = useState("0");
    const [failed, setFailed] = useState(false);
    const [pdfInfo, setPdfInfo] = useState<PdfInfo | null>(null);
    const [upvoteQuery, setUpvoteQuery] = useState<string>("");
    const [selectedPdfChunk, setSelectedPdfChunk] = useState<Chunk | null>(null);
    const [sources, setSources] = useState<Source[]>([]);
    const [chatMode, setChatMode] = useState(false);
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
    const [ifGuardRailOn, setIfGuardRailOn] = useState(false);

    useEffect(() => {
        const workflowId = searchParams.get('workflowId');
        const generationOn = searchParams.get('ifGenerationOn') === 'true';

        console.log('workflowId', workflowId)
        console.log('generationOn', generationOn)

        setIfGenerationOn(generationOn);

        const fetchWorkflowDetails = async () => {
            try {
                const details = await getWorkflowDetails(workflowId as string);
                console.log('Models:', details.data.models);

                // Filter and find the model with component "search"
                const searchModel = details.data.models.find(model => model.component === 'search');
                const serviceUrl = searchModel ? createDeploymentUrl(searchModel.model_id) : createDeploymentUrl('');

                // Filter and find the model with component "nlp"
                const nlpModel = details.data.models.find(model => model.component === 'nlp');
                const tokenModelUrl = nlpModel ? createTokenModelUrl(nlpModel.model_id) : createTokenModelUrl('');

                if (nlpModel) {
                    setIfGuardRailOn(true)
                }

                const newModelService = new ModelService(serviceUrl, tokenModelUrl, uuidv4());
                setModelService(newModelService);
                newModelService.sources().then(setSources);
            } catch (error) {
                console.error('Failed to fetch workflow details:', error);
                alert('Failed to fetch workflow details:' + error)
            }
        };

        if (workflowId) {
            fetchWorkflowDetails();
        }
    }, []);

    useEffect(() => {
        if (modelService) {
            setOpacity("100%");
        }
    }, [modelService]);

    const websocketRef = useRef<WebSocket | null>(null);

    async function getResults(
        query: string,
        topK: number,
        queryId?: string,
    ): Promise<SearchResult | null> {
        setFailed(false);
        return modelService!
            .predict(
                /* queryText= */ query,
                /* topK= */ topK,
                /* queryId= */ queryId,
            )
            .then((searchResults) => {
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
                console.log("Prediction error:", e);
                setFailed(true);
                return null;
            });
    }

    interface PiiMapValue {
        id: number;
        originalToken: string;
        tag: string;
    }

    const [queryInfo, setQueryInfo] = useState<{
        cachedQuery: string;
        userQuery: string;
        isDifferent: boolean;
    } | null>(null);

    async function submit(query: string, genaiPrompt: string, bypassCache = false) {
        function replacePlaceholdersWithOriginal(text: string, piiMap: Map<string, PiiMapValue>): string {
            const placeholderPattern = /\[([A-Z]+) #(\d+)\]/g;
            return text.replace(placeholderPattern, (match, tag, id) => {
                // Find the original value in piiMap by ID
                for (const [originalSentence, value] of piiMap.entries()) {
                    if (value.id.toString() === id && value.tag === tag) {
                        return originalSentence;
                    }
                }
                return match; // Return the placeholder if no match is found (should not happen)
            });
        }

        async function replacePIIWithPlaceholders(content: string, piiMap: Map<string, PiiMapValue>): Promise<string> {
            function getSubstringOverlap(str1: string, str2: string): number {
                const len1 = str1.length;
                const len2 = str2.length;

                let maxOverlap = 0;
                for (let i = 0; i < len1; i++) {
                    for (let j = 0; j < len2; j++) {
                        let overlap = 0;
                        while (i + overlap < len1 && j + overlap < len2 && str1[i + overlap] === str2[j + overlap]) {
                            overlap++;
                        }
                        maxOverlap = Math.max(maxOverlap, overlap);
                    }
                }
                return maxOverlap;
            }

            const prediction = await modelService!.piiDetect(content);
            const { tokens, predicted_tags } = prediction;

            // Step 1: Concatenate tokens into sentences
            let sentences: string[] = [];
            let sentenceTags: string[] = [];
            let currentSentence = '';
            let currentTag = '';

            for (let i = 0; i < tokens.length; i++) {
                const word = tokens[i];
                if (! (predicted_tags && predicted_tags[i])) {
                    continue
                }
                const tag = predicted_tags[i][0];
                // console.log('tag:', tag)

                if (tag === currentTag) {
                    currentSentence += ` ${word}`;
                } else {
                    if (currentSentence) {
                        sentences.push(currentSentence.trim());
                        sentenceTags.push(currentTag);
                    }
                    currentSentence = word;
                    currentTag = tag;
                }
            }

            // Push the last sentence and tag
            if (currentSentence) {
                sentences.push(currentSentence.trim());
                sentenceTags.push(currentTag);
            }

            // console.log('sentences:', sentences)
            // console.log('sentenceTags:', sentenceTags)


            // Step 2: Operate on the level of sentences
            let currentId = piiMap.size + 1;
            const processedSentences = sentences.map((sentence, index) => {
                const tag = sentenceTags[index];

                if (tag !== 'O') {
                    // Filter existing entries in piiMap by the same tag
                    const filteredMapEntries = Array.from(piiMap.entries()).filter(([_, value]) => value.tag === tag);

                    let matchedEntry: [string, PiiMapValue] | undefined;

                    // Check for substring overlap
                    for (const [existingToken, value] of filteredMapEntries) {
                        if (getSubstringOverlap(sentence, value.originalToken) > 5) {
                            matchedEntry = [existingToken, value];
                            break;
                        }
                    }

                    if (matchedEntry) {
                        return `[${tag} #${matchedEntry[1].id}]`;
                    } else {
                        piiMap.set(sentence, { id: currentId, originalToken: sentence, tag });
                        currentId++;
                        return `[${tag} #${piiMap.get(sentence)?.id}]`;
                    }
                } else {
                    return sentence;
                }
            });

            return processedSentences.join(" ");
        }

        if (websocketRef.current) {
            websocketRef.current.close();
        }
        setAnswer("");
        setUpvoteQuery(query);
        setResults({ queryId: "", query: "", references: [] });
        setCheckedIds(new Set<number>());
        setCanSearchMore(true);
        setNumReferences(c.numReferencesFirstLoad);

        if (query.trim().length > 0) {
            if (ifGuardRailOn) {
                // Case 1: Guardrail is ON
                const piiMap = new Map<string, PiiMapValue>();

                const results = await getResults(
                    query,
                    c.numReferencesFirstLoad + 1 * c.numReferencesLoadMore
                );

                if (results && ifGenerationOn) {
                    const processedReferences = await Promise.all(
                        results.references.map(async (reference) => {
                            const processedContent = await replacePIIWithPlaceholders(reference.content, piiMap);
                            return { ...reference, content: processedContent };
                        })
                    );

                    const processedQuery = await replacePIIWithPlaceholders(query, piiMap);

                    console.log('processedQuery:', processedQuery);
                    console.log('piiMap:', piiMap);
                    console.log('processedReferences:');
                    processedReferences.forEach(reference => {
                        console.log(reference.content);
                    });

                    modelService!.generateAnswer(
                        processedQuery,
                        `${genaiPrompt}. [TAG #id] is sensitive information replaced as a placeholder, use them in your response for consistency.`,
                        processedReferences,
                        websocketRef,
                        (next) => {
                            setAnswer((prev) => {
                                // Concatenate previous answer and the new part
                                const fullAnswer = prev + next;

                                // Replace placeholders in the concatenated string
                                const replacedAnswer = replacePlaceholdersWithOriginal(fullAnswer, piiMap);

                                // Return the final processed answer to update the state
                                return replacedAnswer;
                            });
                        },
                    );
                }
            } else {
                // Case 2: Guardrail is OFF (Normal generation)
                const results = await getResults(
                    query,
                    c.numReferencesFirstLoad + 1 * c.numReferencesLoadMore
                );

                if (results && ifGenerationOn) {
                    const modelId = modelService?.getModelID();

                    if (!bypassCache) {
                        try {
                            const cachedResult = await fetchCachedGeneration(modelId!, query);
                            console.log('cachedResult', cachedResult);

                            if (cachedResult && cachedResult.llm_res) {
                                console.log('cached query is', cachedResult.query);
                                console.log('cached generation is', cachedResult.llm_res);

                                const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
                                for (const token of cachedResult.llm_res.split(' ')) {
                                    setAnswer((prev) => prev + " " + token);
                                    await sleep(20);
                                }

                                // setAnswer(cachedResult.llm_res); // Directly use the cached result if available

                                // Set the query information including whether they differ
                                setQueryInfo({
                                    cachedQuery: cachedResult.query,
                                    userQuery: query,
                                    isDifferent: cachedResult.query !== query
                                });

                                return; // Stop further execution since the answer was found in cache
                            }
                        } catch (error) {
                            console.error('Failed to retrieve cached result:', error);
                            // Continue to generate a new answer if there's an error in fetching from the cache
                        }
                    }

                    // No cache hit or cache not used, proceed with generation
                    setQueryInfo(null); // Indicates no cached data was used

                    modelService!.generateAnswer(
                        query,
                        genaiPrompt,
                        results.references,
                        websocketRef,
                        (next) => setAnswer((prev) => prev + next),
                    );
                }
            }
        } else {
            setResults(null);
            setAnswer("");
        }
    }


    function regenerateWithSelectedReferences() {
        setAnswer("");
        modelService!.generateAnswer(
            query,
            prompt,
            results!.references.filter((ref) => checkedIds.has(ref.id)),
            websocketRef,
            (next) => setAnswer((prev) => prev + next),
        );
    }

    function chooseExample(example: string) {
        setQuery(example);
        submit(example, prompt);
    }

    function openSource(ref: ReferenceInfo) {
        if (!ref.sourceName.toLowerCase().endsWith(".pdf")) {
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
                alert("Failed to open PDF. Please try again soon.");
                console.log("Failed to open PDF", e);
            });
    }

    function upvote(refId: number, content: string) {
        modelService!.upvote(
            /* queryId= */ results!.queryId,
            /* queryText= */ results!.query,
            /* referenceId= */ refId,
            /* referenceText= */ content,
        );
    }

    function downvote(refId: number, content: string) {
        modelService!.downvote(
            /* queryId= */ results!.queryId,
            /* queryText= */ results!.query,
            /* referenceId= */ refId,
            /* referenceText= */ content,
        );
    }

    const moreInBuffer = results && results.references.length > numReferences;
    const showMoreButton = canSearchMore || moreInBuffer;

    function more() {
        const newNumReferences = numReferences + c.numReferencesLoadMore;
        const bufferCoversNextLoad =
            results!.references.length >= newNumReferences;
        if (canSearchMore && !bufferCoversNextLoad) {
            getResults(query, newNumReferences, results!.queryId).then(() =>
                setNumReferences(newNumReferences),
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
                    <div style={{ height: "100%", width: "100%" }}>

                        {pdfInfo && (
                            <PdfViewerWrapper>
                                <PdfViewer
                                    name={pdfInfo.filename}
                                    src={pdfInfo.source}
                                    chunks={pdfInfo.docChunks}
                                    initialChunk={
                                        pdfInfo.highlighted
                                    }
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
                                    upvoteText={
                                        selectedPdfChunk.text
                                    }
                                    onSubmit={() => {
                                        modelService.upvote(
                                            results!.queryId,
                                            upvoteQuery,
                                            selectedPdfChunk.id,
                                            selectedPdfChunk.text,
                                        );
                                    }}
                                />
                            </UpvoteModalWrapper>
                        )}
                        <a href="/">
                            <Logo src={LogoImg.src} alt="Logo" />
                        </a>
                        <TopRightCorner>
                            <ChatToggle
                                active={chatMode}
                                onClick={() =>
                                    setChatMode(
                                        (chatMode) => !chatMode,
                                    )
                                }
                            />
                            <Spacer $width="40px" />
                            <Teach />
                        </TopRightCorner>
                        {chatMode ? (
                            <Chat />
                        ) : (
                            <>
                                <SearchContainer
                                    $center={results === null}
                                >
                                    {!results && (
                                        <Pad
                                            $left="5px"
                                            $bottom="5px"
                                        >
                                            <CardTitle>
                                                How can we help?
                                            </CardTitle>
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
                                    />
                                    {failed && (
                                        <Pad $top="100px">
                                            <InvalidModelMessage />
                                        </Pad>
                                    )}
                                </SearchContainer>
                                {results && !failed && (
                                    <Pad
                                        $top="150px"
                                        $bottom="80px"
                                        $left="10%"
                                        $right="30%"
                                    >
                                        <Pad $left="5px">
                                            {
                                                ifGenerationOn &&
                                                <>
                                                    <Spacer $height="30px" />
                                                    <GeneratedAnswer
                                                        answer={answer}
                                                        regenerateAndBypassCache={() => {
                                                            submit(query, prompt, true)
                                                        }}
                                                        queryInfo={queryInfo}
                                                    />
                                                </>
                                            }
                                            <Spacer $height="50px" />
                                            {checkedIds.size >
                                                0 && (
                                                    <PillButton
                                                        onClick={
                                                            regenerateWithSelectedReferences
                                                        }
                                                    >
                                                        Regenerate with
                                                        selected
                                                        references
                                                    </PillButton>
                                                )}
                                            <Spacer $height="50px" />
                                            <ReferenceList
                                                references={results.references.slice(
                                                    0,
                                                    numReferences,
                                                )}
                                                onOpen={openSource}
                                                onUpvote={upvote}
                                                onDownvote={
                                                    downvote
                                                }
                                                onMore={more}
                                                showMoreButton={
                                                    !!showMoreButton
                                                }
                                                checkedIds={
                                                    checkedIds
                                                }
                                                onCheck={onCheck}
                                                modelService={modelService}
                                                ifGuardRailOn={ifGuardRailOn}
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