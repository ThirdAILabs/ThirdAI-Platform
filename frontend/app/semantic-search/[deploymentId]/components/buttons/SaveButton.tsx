import React from 'react';
import { FaSave } from 'react-icons/fa';
import { Button } from '@mui/material';

export default function SaveButton(props: { onClick: () => void }) {
  return (
    <Button
      variant="contained"
      color="primary"
      style={{
        width: '48px',
        height: '48px',
        minWidth: 'unset',
        padding: '12px',
      }}
      onClick={props.onClick}
    >
      <FaSave style={{ fontSize: '24px' }} />
    </Button>
  );
}
