import styled from 'styled-components';
import React from 'react';
import { borderRadius, color, fontSizes, padding, shadow } from '../../stylingConstants';
import NotifyingClickable from '../buttons/NotifyingButton';
import PillButton from '../buttons/PillButton';
import { Pad, Spacer } from '../Layout';

const Container = styled.section`
  display: flex;
  flex-direction: column;
  width: 100%;
  height: fit-content;
  background-color: white;
  padding: ${padding.card};
  border-radius: ${borderRadius.card};
  box-shadow: ${shadow.card};
  box-sizing: border-box;
`;

const Label = styled.section`
  font-weight: bold;
  font-size: ${fontSizes.s};
`;

const TextInput = styled.textarea`
  background-color: ${color.textInput};
  font-size: ${fontSizes.m};
  padding: 10px 10px 13px 10px;
  border-radius: ${borderRadius.textInput};
  border: none;
  height: 100px;
  resize: none;
  font-family: Helvetica, Arial, sans-serif;
  line-height: 1;
`;

const UpvotedText = styled.section`
  background-color: white;
  font-size: ${fontSizes.s};
  border-radius: ${borderRadius.textInput};
  border: none;
  max-height: 400px;
  width: 100%;
  resize: none;
  font-family: Helvetica, Arial, sans-serif;
  line-height: 1;
`;

const ButtonContainer = styled.section`
  width: 100%;
  display: flex;
  flex-direction: row;
  justify-content: center;
`;

interface UpvoteModalProps {
  queryText: string;
  setQueryText: (query: string) => void;
  upvoteText: string;
  onSubmit: () => void;
}

export default function UpvoteModal({
  queryText,
  setQueryText,
  upvoteText,
  onSubmit,
}: UpvoteModalProps) {
  return (
    <Container>
      <Pad $left="2px">
        <Label>Query</Label>
      </Pad>
      <Spacer $height="5px" />
      <TextInput value={queryText} onChange={(e) => setQueryText(e.target.value)} />
      <Spacer $height="15px" />
      <Pad $left="2px">
        <Label>Intended Answer</Label>
        <Spacer $height="5px" />
        <UpvotedText>...{upvoteText}...</UpvotedText>
      </Pad>

      <Spacer $height="15px" />
      <ButtonContainer>
        <NotifyingClickable text={'Feedback received!'} onClick={onSubmit}>
          <PillButton>Upvote</PillButton>
        </NotifyingClickable>
      </ButtonContainer>
    </Container>
  );
}
