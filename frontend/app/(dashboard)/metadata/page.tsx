// /app/metadata/page.tsx
'use client';

import React from 'react';
import MetadataTable from './MetadataTable';
import { Typography, Container, Box } from '@mui/material';

const MetadataPage: React.FC = () => {
  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Metadata Management
        </Typography>
        {/* Future: Add buttons or links here */}
      </Box>
      <MetadataTable />
    </Container>
  );
};

export default MetadataPage;
