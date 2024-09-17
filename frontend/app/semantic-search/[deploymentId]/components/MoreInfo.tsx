import React from 'react';
import styled from 'styled-components';
import { borderRadius, color, duration, fontSizes } from '../stylingConstants';

const Container = styled.section`
  width: 18px;
  height: 18px;
  overflow: hidden;

  &:hover {
    overflow: visible;
  }
`;

const Circle = styled.section`
  border-radius: 100%;
  width: 16px;
  height: 16px;
  border: 1px solid ${color.accent};
  display: flex;
  flex-direction: column;
  justify-content: center;
  &:hover {
    cursor: help;
  }
`;

const I = styled.section`
  position: relative;
  top: 1px;
  text-align: center;
  color: ${color.accent};
  font-family: 'Courier New', Courier, monospace;
  font-weight: normal;
  font-size: ${fontSizes.s};
`;

const Info = styled.section<{ $width: string }>`
  width: ${(props) => props.$width};
  background-color: ${color.accent};
  color: white;
  border-radius: ${borderRadius.smallButton};
  padding: 10px;
  padding-bottom: 7px;
  position: relative;
  top: 5px;
  font-size: ${fontSizes.s};
  font-weight: normal;
  opacity: 0;
  transition-duration: ${duration.transition};

  ${Container}:hover & {
    opacity: 100%;
  }
`;

interface MoreInfoProps {
  info: string;
  width: string;
}

export default function MoreInfo({ info, width }: MoreInfoProps) {
  return (
    <Container>
      <Circle>
        <I>i</I>
      </Circle>
      <Info $width={width}>{info}</Info>
    </Container>
  );
}
