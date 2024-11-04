import React from 'react';
import styled from 'styled-components';
import PromptSVG from '../../assets/icons/prompt.svg';
import { Button } from '@mui/material';

const PromptIcon = styled(PromptSVG)`
  margin-bottom: -10px;
  width: 25px;
  path {
    fill: white;
  }
`;

export default function PromptToggle(props: { onClick: () => void }) {
  return (
    <Button style={{ height: '100%' }} onClick={props.onClick} variant="contained">
      <PromptIcon />
    </Button>
  );
}
