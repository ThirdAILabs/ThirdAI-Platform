import React from 'react';
import styled from 'styled-components';
import { borderRadius, color, fontSizes, shadow } from '../stylingConstants';
import { Pad, Spacer } from './Layout';
import PillButton from './buttons/PillButton';
import NotifyingClickable from './buttons/NotifyingButton';

const Panel = styled.section`
  display: flex;
  flex-direction: column;
  padding: 10px;
  box-shadow: ${shadow.card};
  border-radius: ${borderRadius.card};
  background-color: white;
`;

const Label = styled.section`
  font-weight: bold;
  font-size: ${fontSizes.s};
`;

const TextInput = styled.textarea`
  background-color: ${color.textInput};
  font-size: ${fontSizes.s};
  padding: 10px 10px 13px 10px;
  border-radius: ${borderRadius.textInput};
  border: none;
  height: 100px;
  resize: none;
  font-family: Helvetica, Arial, sans-serif;
`;

const ButtonContainer = styled.section`
  width: 100%;
  display: flex;
  flex-direction: row;
  justify-content: center;
`;

interface TeachPanelProps {
  question: string;
  answer: string;
  canAddAnswer: boolean;
  setQuestion: (question: string) => void;
  setAnswer: (answer: string) => void;
  onAssociate: (question: string, answer: string) => void;
  onAddAnswer: (question: string, answer: string) => void;
}

export default function TeachPanel({
  question,
  answer,
  canAddAnswer,
  setQuestion,
  setAnswer,
  onAssociate,
  onAddAnswer,
}: TeachPanelProps) {
  function button(
    buttonText: string,
    notification: string,
    onSubmit: (question: string, answer: string) => void
  ) {
    return (
      <ButtonContainer>
        <NotifyingClickable text={notification} onClick={() => onSubmit(question, answer)}>
          <PillButton>{buttonText}</PillButton>
        </NotifyingClickable>
      </ButtonContainer>
    );
  }

  return (
    <Panel>
      <Pad $left="2px">
        <Label>Teach</Label>
      </Pad>
      <Spacer $height="10px" />
      <TextInput
        placeholder="Question goes here"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <Spacer $height="10px" />
      <TextInput
        placeholder="Answer goes here"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
      />
      <Spacer $height="15px" />
      {button('Associate', 'Feedback received!', onAssociate)}
      <Spacer $height="15px" />
    </Panel>
  );
}
