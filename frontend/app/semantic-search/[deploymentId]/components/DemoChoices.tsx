import React from "react";
import styled from "styled-components";
import { demoSearchParam, demos } from "../assets/demos";
import {
    borderRadius,
    color,
    duration,
    fontSizes,
    padding,
} from "../stylingConstants";
import { Spacer } from "./Layout";

const Description = styled.section`
    font-size: ${fontSizes.s};
    color: ${color.subtext};
    display: flex;
    flex-direction: row;
    align-items: center;
`;

const DemoChoiceButton = styled.button<{ $selected: boolean }>`
    background-color: ${(props) => (props.$selected ? color.accent : "white")};
    border: 1px solid ${(props) => (props.$selected ? "white" : color.accent)};
    border-radius: ${borderRadius.smallButton};
    transition-duration: ${duration.transition};
    font-size: ${fontSizes.s};
    font-weight: normal;
    color: ${(props) => (props.$selected ? "white" : color.accent)};
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

interface DemoChoicesProps {
    currentDemo: keyof typeof demos;
}

export default function DemoChoices({ currentDemo }: DemoChoicesProps) {
    return (
        <Description>
            Use documents for
            {Object.keys(demos).map((key, i) => (
                <>
                    <Spacer $width="7px" />
                    <a href={`?${demoSearchParam}=${key}`}>
                        <DemoChoiceButton $selected={key === currentDemo}>
                            {demos[key as keyof typeof demos].name}
                        </DemoChoiceButton>
                    </a>
                </>
            ))}
        </Description>
    );
}
