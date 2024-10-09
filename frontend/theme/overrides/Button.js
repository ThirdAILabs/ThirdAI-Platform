import { alpha } from '@mui/material/styles';

// ----------------------------------------------------------------------

const COLORS = ['primary', 'secondary', 'info', 'success', 'warning', 'error'];

export default function Button(theme) {
  const isLight = theme.palette.mode === 'light';

  const rootStyle = (ownerState) => {
    const inheritColor = ownerState.color === 'inherit';

    const containedVariant = ownerState.variant === 'contained';

    const outlinedVariant = ownerState.variant === 'outlined';

    const textVariant = ownerState.variant === 'text';

    const softVariant = ownerState.variant === 'soft';

    const smallSize = ownerState.size === 'small';

    const largeSize = ownerState.size === 'large';

    const defaultStyle = {
      textTransform: 'none',
      ...(inheritColor && {
        // CONTAINED
        ...(containedVariant && {
          color: theme.palette.grey[800],
          '&:hover': {
            boxShadow: theme.customShadows.z8,
            backgroundColor: theme.palette.grey[400],
          },
        }),
        // OUTLINED
        ...(outlinedVariant && {
          borderColor: alpha(theme.palette.grey[500], 0.32),
          '&:hover': {
            borderColor: theme.palette.text.primary,
            backgroundColor: theme.palette.action.hover,
          },
        }),
        // TEXT
        ...(textVariant && {
          '&:hover': {
            backgroundColor: theme.palette.action.hover,
          },
        }),
        // SOFT
        ...(softVariant && {
          color: theme.palette.text.primary,
          backgroundColor: alpha(theme.palette.grey[500], 0.08),
          '&:hover': {
            backgroundColor: alpha(theme.palette.grey[500], 0.24),
          },
        }),
      }),
    };

    const colorStyle = COLORS.map((color) => ({
      ...(ownerState.color === color && {
        // CONTAINED
        ...(containedVariant && {
          '&:hover': {
            boxShadow: theme.customShadows[color],
          },
        }),
        // SOFT
        ...(softVariant && {
          color: theme.palette[color][isLight ? 'dark' : 'light'],
          backgroundColor: alpha(theme.palette[color].main, 0.16),
          '&:hover': {
            backgroundColor: alpha(theme.palette[color].main, 0.32),
          },
        }),
      }),
    }));

    // ***** New Code to add light blue color for 'contained' variant *****
    const containedLightBlue = {
      ...(containedVariant && {
        backgroundColor: theme.palette.primary.main, // Light Blue color
        color: theme.palette.common.white,
        '&:hover': {
          backgroundColor: alpha(theme.palette.primary.darker, 0.85), // Slightly darker blue on hover
        },
      }),
    };

    // ***** New Code for Delete Button with Red Color *****
    const containedRedDelete = {
      ...(containedVariant &&
        ownerState.color === 'error' && {
          backgroundColor: theme.palette.error.main, // Red color for delete
          color: theme.palette.common.white,
          '&:hover': {
            backgroundColor: theme.palette.error.dark, // Darker red on hover
          },
        }),
    };

    // ***** New Code for Delete Button with Red Color *****
    const containedGreenSuccess = {
      ...(containedVariant &&
        ownerState.color === 'success' && {
          backgroundColor: theme.palette.success.main,
          color: theme.palette.common.white,
          '&:hover': {
            backgroundColor: theme.palette.success.dark,
          },
        }),
    };

    const disabledState = {
      '&.Mui-disabled': {
        // SOFT
        ...(softVariant && {
          backgroundColor: theme.palette.action.disabledBackground,
        }),
      },
    };

    const size = {
      ...(smallSize && {
        height: 30,
        fontSize: 13,
        ...(softVariant && {
          padding: '4px 10px',
        }),
      }),
      ...(largeSize && {
        height: 48,
        fontSize: 15,
        ...(softVariant && {
          padding: '8px 22px',
        }),
      }),
    };

    // ***** Adding the new style to the return object *****
    return [
      containedLightBlue,
      containedRedDelete,
      containedGreenSuccess,
      ...colorStyle,
      defaultStyle,
      disabledState,
      size,
    ];
  };

  return {
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },

      styleOverrides: {
        root: ({ ownerState }) => rootStyle(ownerState),
      },
    },
  };
}
