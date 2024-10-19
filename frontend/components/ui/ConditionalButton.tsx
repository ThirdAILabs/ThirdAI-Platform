import React from 'react';
import { Tooltip, Button, ButtonProps } from '@mui/material';

interface ConditionalButtonProps extends ButtonProps {
  isDisabled: boolean;
  tooltipMessage: string;
}
/**
 * A button that is only enabled when a certain condition is met.
 * If the enabling condition is not met, a tooltip appears to explain
 * why it is disabled.
 */
const ConditionalButton: React.FC<ConditionalButtonProps> = ({
  isDisabled,
  tooltipMessage,
  children,
  ...rest
}) => {
  return (
    <Tooltip title={isDisabled ? tooltipMessage : ''} arrow>
      <span
        style={{
          width: '100%',
          display: 'inline-block',
          cursor: isDisabled ? 'not-allowed' : 'pointer',
        }}
      >
        <Button
          disabled={isDisabled}
          style={{
            pointerEvents: isDisabled ? 'none' : 'auto',
          }}
          {...rest} // Spread the remaining props (variant, color, etc.)
        >
          {children}
        </Button>
      </span>
    </Tooltip>
  );
};

export default ConditionalButton;
