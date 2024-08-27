import React from "react";
import styled from "styled-components";
import { color, fontSizes } from "../stylingConstants";
import { Spacer } from "./Layout";
import MoreInfo from "./MoreInfo";
// import { ReactMarkdown } from "react-markdown/lib/react-markdown";
import ReactMarkdown from "react-markdown";
import TypingAnimation from "./TypingAnimation";

interface GeneratedAnswerProps {
    answer: string;
    regenerateAndBypassCache?: () => void;  // Function to trigger regeneration of the original query
    queryInfo?: {
        cachedQuery: string;
        userQuery: string;
        isDifferent: boolean;
    } | null; // Accept null as a possible type
    cacheEnabled: boolean;
    setCacheEnabled: (enabled: boolean) => void; // Update to accept a boolean argument
}

const Container = styled.section`
    display: flex;
    flex-direction: column;
    justify-content: space-between;
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
    "This answer has been generated using AI based on resources in the " +
    "knowledgebase. Generative AI is experimental and may " +
    "not find the appropriate answer sometimes.";

export default function GeneratedAnswer({ answer, queryInfo, regenerateAndBypassCache, cacheEnabled, setCacheEnabled }: GeneratedAnswerProps) {
    return (
        <Container>
            <Header>
                Generated Answer
                <Spacer $width="10px" />
                <div className="flex items-center">
                    <span className="mr-2">Use Cache</span>
                    <button
                        onClick={() => setCacheEnabled(!cacheEnabled)}
                        className={`relative inline-flex items-center h-6 rounded-full w-11 transition-colors duration-300 focus:outline-none ${
                            cacheEnabled ? 'bg-blue-500' : 'bg-gray-300'
                        }`}
                    >
                        <span
                            className={`transform transition-transform duration-300 inline-block w-4 h-4 bg-white rounded-full ${
                                cacheEnabled ? 'translate-x-6' : 'translate-x-1'
                            }`}
                        />
                    </button>
                </div>
                <MoreInfo info={`This toggle controls whether to use the cache during generation. ${disclaimer}`} width="240px" />
            </Header>
            {queryInfo && queryInfo.isDifferent && (
                <div className="text-sm mb-2">
                    Showing result for '{queryInfo.cachedQuery}'
                    <br />
                    <a onClick={regenerateAndBypassCache} style={{ cursor: 'pointer', color: 'blue', textDecoration: 'underline' }}>
                        Search instead for '{queryInfo.userQuery}'
                    </a>
                </div>
            )}
            {answer.length === 0 ? (
                <>
                    <Spacer $height="20px" />
                    <TypingAnimation />
                </>
            ) : (
                <Answer>
                    <ReactMarkdown>{answer}</ReactMarkdown>
                </Answer>
            )}

            <Spacer $height="50px" />
            <Divider />
        </Container>
    );
}
