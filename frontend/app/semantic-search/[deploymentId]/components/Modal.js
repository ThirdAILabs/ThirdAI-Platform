import React from "react";
import styled from "styled-components";

const ModalContainer = styled.div`
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background-color: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
    z-index: 1000;
    max-width: 400px;
    width: 100%;
`;

const Overlay = styled.div`
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 999;
`;

export default function Modal({ children, onClose }) {
    return (
        <>
            <Overlay onClick={onClose} />
            <ModalContainer>{children}</ModalContainer>
        </>
    );
}
