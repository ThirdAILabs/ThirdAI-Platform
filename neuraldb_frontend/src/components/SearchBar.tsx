import React, { useCallback, useContext, useRef, useState } from "react";
import styled from "styled-components";
import { FaSave } from "react-icons/fa";
import {
    borderRadius,
    color,
    duration,
    fontSizes,
    padding,
} from "../stylingConstants";
import { Spacer } from "./Layout";
import { ModelService, Source } from "../modelServices";
import { ModelServiceContext } from "../Context";
import Sources from "./Sources";
import useClickOutside from "./hooks/useClickOutside";
import PromptToggle from "./buttons/PromptToggle";
import SearchTextInput from "./SearchTextInput";
import Modal from "./Modal";

const Container = styled.section`
    background-color: white;
    box-shadow: 0 10px 10px 4px white;
    width: 100%;
    display: flex;
    flex-direction: column;
    padding: 5px;
    padding-top: 10px;
`;

const SearchArea = styled.section`
    background-color: white;
    width: 100%;
    display: flex;
    flex-direction: row;
    align-items: center;
`;

const Description = styled.section`
    font-size: ${fontSizes.s};
    color: ${color.subtext};
    display: flex;
    flex-direction: row;
    align-items: center;
`;

const TryNewModelButton = styled.button`
    background-color: white;
    border: 1px solid ${color.accent};
    border-radius: ${borderRadius.smallButton};
    transition-duration: ${duration.transition};
    font-size: ${fontSizes.s};
    font-weight: normal;
    color: ${color.accent};
    width: fit-content;
    padding: ${padding.smallButton};

    &:hover {
        background-color: ${color.accent};
        color: white;
        cursor: pointer;
    }

    &:active {
        background-color: ${color.accentDark};
    }
`;

const PanelContainer = styled.section`
    position: relative;
    height: 0;
    overflow-y: visible;
`;

const SaveIcon = styled(FaSave)`
    margin-left: 10px;
    cursor: pointer;
    color: ${color.accent};

    &:hover {
        color: ${color.accentDark};
    }
`;

const ButtonGroup = styled.div`
    display: flex;
    justify-content: space-between;
    margin-top: 20px;
`;

interface ButtonProps {
    primary?: boolean;
}

const Button = styled.button<ButtonProps>`
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    background-color: ${(props) => (props.primary ? "#4CAF50" : "#f1f1f1")};
    color: ${(props) => (props.primary ? "white" : "black")};
    cursor: pointer;
    font-size: 14px;

    &:hover {
        background-color: ${(props) => (props.primary ? "#45a049" : "#ddd")};
    }
`;

const Input = styled.input`
    width: calc(100% - 120px);
    padding: 10px;
    margin-top: 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
`;

const ErrorMessage = styled.p`
    color: red;
    font-size: 12px;
    margin-top: 5px;
`;

interface UserModelDescriptionProps {
    onClickViewDocuments: () => void;
}

function UserModelDescription(props: UserModelDescriptionProps) {
    return (
        <Description>
            Generating answers from your documents.
            <Spacer $width="7px" />
            <TryNewModelButton onClick={props.onClickViewDocuments}>
                View Documents
            </TryNewModelButton>
            {/* <Spacer $width="7px" />
            <a href={process.env.REACT_APP_MODEL_BAZAAR_URL}>
                <TryNewModelButton>Train/Deploy new models</TryNewModelButton>
            </a> */}
        </Description>
    );
}

function GlobalModelDescription() {
    return (
        <Description>
            Generating answers from knowledgebase documents, or
            <Spacer $width="7px" />
            <a href={process.env.REACT_APP_MODEL_BAZAAR_URL}>
                <TryNewModelButton>use your own documents</TryNewModelButton>
            </a>
        </Description>
    );
}

interface SearchBarProps {
    query: string;
    setQuery: (query: string) => void;
    onSubmit: (query: string, genaiPrompt: string) => void;
    sources: Source[];
    setSources: (sources: Source[]) => void;
    prompt: string;
    setPrompt: (prompt: string) => void;
}

export default function SearchBar({
    query,
    setQuery,
    onSubmit,
    sources,
    setSources,
    prompt,
    setPrompt,
}: SearchBarProps) {
    const modelService = useContext<ModelService>(ModelServiceContext);
    const [showSources, setShowSources] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [modelName, setModelName] = useState("");
    const [showModelNameInput, setShowModelNameInput] = useState(false);
    const [error, setError] = useState("");

    const sourcesRef = useRef<HTMLElement>();
    const handleClickOutside = useCallback(() => {
        setShowSources(false);
    }, []);

    useClickOutside(sourcesRef, handleClickOutside);

    const handleSaveClick = () => {
        setModalOpen(true);
        setShowModelNameInput(false);
        setError("");
    };

    const handleShowModelNameInput = () => {
        setError(""); // Clear any previous errors
        setShowModelNameInput(true);
    };

    const handleBack = () => {
        setError(""); // Clear any previous errors
        setShowModelNameInput(false);
    };

    const handleOverride = () => {
        modelService
            .saveModel(true)
            .then(() => {
                setModalOpen(false);
                setError("");
            })
            .catch((error) => {
                console.error("Error overriding model:", error);
                const errorMessage =
                    typeof error === "string"
                        ? error
                        : error.message || JSON.stringify(error);
                setError(errorMessage);
            });
    };

    const handleSaveAsNew = () => {
        if (modelName.trim() === "") {
            setError("Model name is required.");
            return;
        }

        modelService
            .saveModel(false, modelName)
            .then(() => {
                setModalOpen(false);
                setError("");
            })
            .catch((error) => {
                console.error("Error overriding model:", error);
                const errorMessage =
                    typeof error === "string"
                        ? error
                        : error.message || JSON.stringify(error);
                setError(errorMessage);
            });
    };

    return (
        <Container>
            <SearchArea>
                <SearchTextInput
                    placeholder="Ask anything..."
                    onSubmit={() => {
                        onSubmit(query, prompt)

                        // Create a telemetry event
                        const event = {
                            UserAction: 'Searched query',
                            UIComponent: 'SearchTextInput',
                            UI: 'SearchBar',
                            data: {
                                query: query
                            }
                        };

                        // Record the event
                        modelService.recordEvent(event)
                            .then(data => {
                                console.log("Event recorded successfully:", data);
                            })
                            .catch(error => {
                                console.error("Error recording event:", error);
                            });

                    }}
                    value={query}
                    setValue={setQuery}
                />
                <PromptToggle
                    active={dialogOpen}
                    onClick={() => setDialogOpen((dialogOpen) => !dialogOpen)}
                />
                <SaveIcon onClick={handleSaveClick} />
            </SearchArea>
            {dialogOpen && (
                <>
                    <Spacer $height="5px" />
                    <SearchTextInput
                        placeholder="Enter custom prompt"
                        onSubmit={() => onSubmit(query, prompt)}
                        value={prompt}
                        setValue={setPrompt}
                    />
                </>
            )}

            <Spacer $height="5px" />
            {modelService.isUserModel() ? (
                <UserModelDescription
                    onClickViewDocuments={() => setShowSources((val) => !val)}
                />
            ) : (
                <GlobalModelDescription />
            )}
            <Spacer $height="5px" />
            <PanelContainer ref={sourcesRef}>
                <Sources
                    sources={sources}
                    visible={showSources}
                    setSources={setSources}
                />
            </PanelContainer>

            {modalOpen && (
                <Modal onClose={() => setModalOpen(false)}>
                    <h2>Save Model</h2>
                    <p>
                        Do you want to override the existing model or save as a
                        new model?
                    </p>
                    {!showModelNameInput ? (
                        <>
                            {error && <ErrorMessage>{error}</ErrorMessage>}
                            <ButtonGroup>
                                <Button onClick={handleOverride}>
                                    Override
                                </Button>
                                <Button
                                    primary
                                    onClick={handleShowModelNameInput}
                                >
                                    Save as New
                                </Button>
                            </ButtonGroup>
                        </>
                    ) : (
                        <>
                            <Input
                                type="text"
                                placeholder="Enter model name"
                                value={modelName}
                                onChange={(e) => setModelName(e.target.value)}
                            />
                            {error && <ErrorMessage>{error}</ErrorMessage>}
                            <ButtonGroup>
                                <Button onClick={handleBack}>Back</Button>
                                <Button primary onClick={handleSaveAsNew}>
                                    Submit
                                </Button>
                            </ButtonGroup>
                        </>
                    )}
                </Modal>
            )}
        </Container>
    );
}
