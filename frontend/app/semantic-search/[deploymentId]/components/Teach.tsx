import React, { useCallback, useContext, useRef, useState } from "react";
import styled from "styled-components";
import { borderRadius, color, duration } from "../stylingConstants";
import TeachSVG from "../assets/icons/teach.svg";
import TeachPanel from "./TeachPanel";
import useClickOutside from "./hooks/useClickOutside";
import { ModelServiceContext } from "../Context";
import { ModelService } from "../modelServices";
import { Button } from "@/components/ui/button";

const Container = styled.section`
    width: 50px;
    height: fit-content;
    display: flex;
    flex-direction: column;
    overflow: visible;
    padding-right: ${borderRadius.card};
    align-items: flex-end;
`;

const TeachIcon = styled(TeachSVG)`
    transition-duration: ${duration.transition};
    width: 40px;
    path {
        stroke: "white";
    }
`;

const PanelContainer = styled.section`
    position: relative;
    right: -${borderRadius.card};
    width: 300px;
`;

export default function Teach() {
    const [showPanel, setShowPanel] = useState(false);
    const [question, setQuestion] = useState("");
    const [answer, setAnswer] = useState("");
    const modelService = useContext<ModelService | null>(ModelServiceContext);

    const containerRef = useRef<HTMLElement | null>(null);

    const handleClickOutside = useCallback(() => {
        setShowPanel(false);
    }, []);

    useClickOutside(containerRef, handleClickOutside);

    function togglePanel() {
        setShowPanel((prev) => !prev);
    }

    return (
        <Container ref={containerRef}>
            <Button style={{width: "60px", height: "50px"}} onClick={togglePanel}>
                <TeachIcon $active={showPanel} />
            </Button>
            {showPanel && (
                <PanelContainer>
                    <TeachPanel
                        question={question}
                        answer={answer}
                        canAddAnswer={true}
                        setQuestion={setQuestion}
                        setAnswer={setAnswer}
                        onAddAnswer={(q, a) => modelService?.qna(q, a)}
                        onAssociate={(q, a) => modelService?.associate(q, a)}
                    />
                </PanelContainer>
            )}
        </Container>
    );
}
