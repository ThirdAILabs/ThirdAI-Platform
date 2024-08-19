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
import { getWorkflowDetails } from '@/lib/backend';

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

    function submit(query: string, genaiPrompt: string) {
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
            getResults(
                query,
                c.numReferencesFirstLoad + 1 * c.numReferencesLoadMore,
            ).then((results) => {
                if (results &&
                    ifGenerationOn // turn on generation only if specified
                ) {
                    modelService!.generateAnswer(
                        query,
                        genaiPrompt,
                        results.references,
                        websocketRef,
                        (next) => setAnswer((prev) => prev + next),
                    );
                }
            });
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
                    <div style={{height: "100%", width: "100%"}}>

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
                                                modelService = {modelService}
                                                ifGuardRailOn = {ifGuardRailOn}
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
