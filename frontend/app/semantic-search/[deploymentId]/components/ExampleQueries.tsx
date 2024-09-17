import React from 'react';
import styled from 'styled-components';
import { duration, fontSizes } from '../stylingConstants';
const Container = styled.section`
  width: 100%;
  display: flex;
  flex-direction: column;
`;

const Header = styled.section`
  font-weight: bold;
  font-size: ${fontSizes.m};
  margin-bottom: 5px;
`;

const Example = styled.section`
  width: fit-content;
  padding-left: 0;
  padding-bottom: 2px;
  margin-bottom: 5px;
  border-bottom: 1.5px solid;
  transition-duration: ${duration.transition};
  font-size: ${fontSizes.s};

  &:hover {
    padding-left: 5px;
    padding-right: 5px;
    transition-duration: ${duration.transition};
    cursor: pointer;
  }

  &:active {
    background-color: rgba(0, 0, 0, 0.1);
  }
`;

interface ExampleQueriesProps {
  examples: string[];
  onClick: (query: string) => void;
}

export default function ExampleQueries({ examples, onClick }: ExampleQueriesProps) {
  return (
    <Container>
      <Header>Examples</Header>
      {examples.map((example, i) => {
        return (
          <Example key={i} onClick={() => onClick(example)}>
            {example}
          </Example>
        );
      })}
    </Container>
  );
}
