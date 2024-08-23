import React, { MouseEventHandler, ReactElement, useState } from "react";
import styled from "styled-components";
import {
    color,
    borderRadius,
    duration,
    fontSizes,
    padding,
} from "../../stylingConstants";

const Container = styled.section`
    display: flex;
    flex-direction: row;
    align-items: center;
`;

const NotificationPositioner = styled.section`
    width: 0;
    overflow-x: visible;
`;

const NotificationContainer = styled.section`
    width: 100vw;
`;

const Notification = styled.section<{ $visible: boolean }>`
    color: white;
    background-color: ${color.accent};
    width: fit-content;
    margin-left: 10px;
    transition-duration: ${duration.transition};
    opacity: ${(props) => (props.$visible ? "100%" : "0")};
    font-size: ${fontSizes.s};
    padding: ${padding.smallButton};
    border-radius: ${borderRadius.smallButton};
`;

interface NotifyingClickableProps {
    children: ReactElement;
    text: string;
    onClick: MouseEventHandler<any>;
    durationMs?: number;
    onDismiss?: () => void;
}

export default function NotifyingClickable({
    children,
    text,
    onClick,
    durationMs = 3000,
    onDismiss = () => {},
}: NotifyingClickableProps) {
    const [notify, setNotify] = useState(false);

    function clickHandler(e: any) {
        setNotify(true);
        onClick(e);
        setTimeout(() => {
            setNotify(false);
            onDismiss();
        }, durationMs);
    }

    return (
        <Container onClick={clickHandler}>
            {children}
            <NotificationPositioner>
                <NotificationContainer>
                    <Notification $visible={notify}>{text}</Notification>
                </NotificationContainer>
            </NotificationPositioner>
        </Container>
    );
}
