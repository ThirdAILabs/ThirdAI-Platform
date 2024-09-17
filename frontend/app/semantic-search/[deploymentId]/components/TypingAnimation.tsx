import React from 'react';
import styled, { keyframes } from 'styled-components';
import { color } from '../stylingConstants';

const Typing = styled.section`
  width: 5em;
  height: 2em;
  position: relative;
  border-radius: 20px;
`;

const loadingFade = keyframes`
    0% {
        opacity: 0;
    }
    50% {
        opacity: 0.8;
    }
    100% {
        opacity: 0;
    }
`;

const TypingDot = styled.section`
  float: left;
  width: 8px;
  height: 8px;
  margin: 0 4px;
  background: ${color.accent};
  border-radius: 50%;
  opacity: 0;
  animation: ${loadingFade} 1s infinite;

  &:nth-child(1) {
    animation-delay: 0s;
  }

  &:nth-child(2) {
    animation-delay: 0.2s;
  }

  &:nth-child(3) {
    animation-delay: 0.4s;
  }
`;

export default function TypingAnimation() {
  return (
    <Typing>
      <TypingDot />
      <TypingDot />
      <TypingDot />
    </Typing>
  );
}
