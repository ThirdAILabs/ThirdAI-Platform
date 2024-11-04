import React from 'react';
import styled from 'styled-components';
import ChatSVG from '../../assets/icons/chat.svg';
import { Button } from '@mui/material';

const ChatIcon = styled(ChatSVG)<{ $active: boolean }>`
  width: 25px;
  margin-top: 2px;
  path {
    fill: white;
  }
`;

export default function ChatToggle(props: { active: boolean; onClick: () => void }) {
  return (
    <Button style={{ width: '60px', height: '50px' }} onClick={props.onClick} variant="contained">
      <ChatIcon $active={props.active} />
    </Button>
  );
}
