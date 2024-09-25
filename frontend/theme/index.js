'use client';

import PropTypes from 'prop-types';
import { useMemo } from 'react';
import { CssBaseline } from '@mui/material';
import {
  createTheme,
  StyledEngineProvider,
  ThemeProvider as MUIThemeProvider,
} from '@mui/material/styles';

import palette from './palette';
import customShadows from './customShadows';
import componentsOverride from './overrides';
import GlobalStyles from './globalStyles';

// Create a ThemeProvider component that wraps MUI's ThemeProvider
export default function ThemeProvider({ children }) {
  const themeOptions = useMemo(
    () => ({
      palette: palette('light'), // Set the default theme mode
      shape: { borderRadius: 8 },
      customShadows: customShadows('light'),
    }),
    []
  );

  const theme = createTheme(themeOptions);

  theme.components = componentsOverride(theme); // Apply component overrides

  return (
    <StyledEngineProvider injectFirst>
      <MUIThemeProvider theme={theme}>
        <CssBaseline /> {/* Apply a baseline CSS reset */}
        <GlobalStyles /> {/* Apply any custom global styles */}
        {children}
      </MUIThemeProvider>
    </StyledEngineProvider>
  );
}

ThemeProvider.propTypes = {
  children: PropTypes.node,
};
