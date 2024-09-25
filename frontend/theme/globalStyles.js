import { GlobalStyles as MUIGlobalStyles } from '@mui/material';

export default function GlobalStyles() {
  const inputGlobalStyles = (
    <MUIGlobalStyles
      styles={{
        '*': {
          boxSizing: 'border-box',
        },
        html: {
          margin: 0,
          padding: 0,
          width: '100%',
          height: '100%',
          WebkitOverflowScrolling: 'touch',
        },
        body: {
          margin: 0,
          padding: 0,
          width: '100%',
          height: '100%',
        },
        '#root': {
          width: '100%',
          height: '100%',
        },
        input: {
          '&[type=number]': {
            MozAppearance: 'textfield',
            '&::-webkit-outer-spin-button': {
              margin: 0,
              WebkitAppearance: 'none',
            },
            '&::-webkit-inner-spin-button': {
              margin: 0,
              WebkitAppearance: 'none',
            },
          },
        },
        img: {
          display: 'block',
          maxWidth: '100%',
        },
        ul: {
          margin: 0,
          padding: 0,
        },

        '.MuiTableRow-root': {
          marginBottom: '10px',
        },

        '.MuiTableRow-root td:first-of-type': {
          borderTopLeftRadius: '12px',
          borderBottomLeftRadius: '12px',
        },

        '.MuiTableRow-root td:last-child': {
          borderTopRightRadius: '12px',
          borderBottomRightRadius: '12px',
        },
        '.fullHeightDialog': {
          '.MuiDialog-paper': {
            borderRadius: `0px !important`,
            height: '100vh',
            minWidth: '350px',
            maxHeight: '100vh',
            margin: 0,
          },
          '.MuiDialog-container': {
            justifyContent: 'end',
          },
        },
      }}
    />
  );

  return inputGlobalStyles;
}
