import React from 'react';
import styled from 'styled-components';
import { Spacer } from './Layout';
import PillButton from './buttons/PillButton';

const Container = styled.section`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
`;

const ButtonsRow = styled.section`
  width: 100%;
  display: flex;
  flex-direction: row;
  justify-content: center;
  padding-top: 30px;
`;

export default function InvalidModelMessage() {
  return (
    <Container>
      We are unable to reach our server. Please check that you entered the right URL.
      <ButtonsRow>
        {/* <a href="/">
                    <PillButton>Use knowledgebase documents</PillButton>
                </a>
                <Spacer $width="20px" /> */}
        <a href="/">
          <PillButton>Back to Model Bazaar</PillButton>
        </a>
      </ButtonsRow>
    </Container>
  );
}
