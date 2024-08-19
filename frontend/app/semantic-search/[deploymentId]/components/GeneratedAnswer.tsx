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

export default function GeneratedAnswer({ answer }: GeneratedAnswerProps) {
    return (
        <Container>
            <Header>
                Generated Answer
                <Spacer $width="10px" />
                <MoreInfo info={disclaimer} width="240px" />
            </Header>
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
