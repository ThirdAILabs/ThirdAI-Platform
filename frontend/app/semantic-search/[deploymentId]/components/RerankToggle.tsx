import React, { useRef } from 'react';
import styled from 'styled-components';
import { borderRadius, color, duration } from '../stylingConstants';

const Container = styled.section`
  height: 30px;
  display: flex;
  flex-direction: column;
  overflow: visible;
  padding-right: ${borderRadius.card};
  align-items: flex-end;
`;

const Button = styled.button<{ $active: boolean }>`
  border: none;
  background-color: ${(props) => (props.$active ? color.accent : 'white')};
  padding: 15px 10px;
  height: 45px;
  border-radius: ${borderRadius.card};
  transition-duration: ${duration.transition};

  &:hover {
    cursor: pointer;
    background-color: ${(props) => (props.$active ? color.accent : color.accentExtraLight)};
  }
`;

const RerankText = styled.text<{ $active: boolean }>`
  color: ${(props) => (props.$active ? 'white' : color.accent)};
`;

export default function RerankToggle({
  state,
  onToggle,
}: {
  state: boolean;
  onToggle: () => void;
}) {
  const containerRef = useRef<HTMLElement>(null);

  function togglePanel() {
    onToggle();
  }

  return (
    <Container ref={containerRef}>
      <Button onClick={togglePanel} $active={state}>
        <RerankText $active={state}>Rerank: {state ? 'On' : 'Off'}</RerankText>
      </Button>
    </Container>
  );
}
