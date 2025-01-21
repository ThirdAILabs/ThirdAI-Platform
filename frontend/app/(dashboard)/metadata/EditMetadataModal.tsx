// EditMetadataModal.tsx
'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  IconButton,
  Grid,
  CircularProgress,
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import { updateDocumentMetadata } from '@/lib/backend';

interface MetadataAttribute {
  attribute_name: string;
  value: string | number;
}

interface DocumentMetadata {
  document_id: string;
  document_name: string;
  metadata_attributes: MetadataAttribute[];
}

interface EditMetadataModalProps {
  document: DocumentMetadata;
  deploymentUrl: string; // Add this prop
  onClose: () => void;
  onSave: (documentId: string, updatedAttributes: MetadataAttribute[]) => void;
}

const EditMetadataModal: React.FC<EditMetadataModalProps> = ({
  document,
  deploymentUrl,
  onClose,
  onSave,
}) => {
  const [attributes, setAttributes] = useState<MetadataAttribute[]>(document.metadata_attributes);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (index: number, field: keyof MetadataAttribute, value: string) => {
    const updated = [...attributes];
    updated[index] = { ...updated[index], [field]: value };
    setAttributes(updated);
  };

  const handleAddAttribute = () => {
    setAttributes([...attributes, { attribute_name: '', value: '' }]);
  };

  const handleRemoveAttribute = (index: number) => {
    const updated = [...attributes];
    updated.splice(index, 1);
    setAttributes(updated);
  };

  const handleSubmit = async () => {
    // Validation: Ensure all fields are filled
    for (const attr of attributes) {
      if (!attr.attribute_name.trim() || attr.value === '') {
        setError('Attribute Name and Value cannot be empty.');
        return;
      }
    }

    setIsLoading(true);
    setError(null);

    try {
      // Convert attributes array to metadata object
      const metadata = attributes.reduce(
        (acc, attr) => {
          acc[attr.attribute_name] = attr.value;
          return acc;
        },
        {} as Record<string, string | number>
      );

      // Call the API to update metadata
      await updateDocumentMetadata(deploymentUrl, document.document_id, { metadata });

      // If successful, update the UI
      onSave(document.document_id, attributes);
      onClose();
    } catch (err) {
      console.error('Error updating metadata:', err);
      setError(err instanceof Error ? err.message : 'Failed to update metadata');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Edit Metadata for {document.document_name}</DialogTitle>
      <DialogContent dividers>
        {error && <div className="text-red-500 mb-4 p-2 bg-red-50 rounded">{error}</div>}

        {attributes.map((attr, index) => (
          <Grid
            container
            spacing={2}
            key={index}
            alignItems="center"
            style={{ marginBottom: '16px' }}
          >
            <Grid item xs={12} sm={5}>
              <TextField
                label="Attribute Name"
                value={attr.attribute_name}
                onChange={(e) => handleChange(index, 'attribute_name', e.target.value)}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12} sm={5}>
              <TextField
                label="Value"
                value={attr.value}
                onChange={(e) => handleChange(index, 'value', e.target.value)}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12} sm={2}>
              <IconButton
                color="error"
                aria-label="remove attribute"
                onClick={() => handleRemoveAttribute(index)}
                disabled={attributes.length === 1} // Prevent removing the last attribute
              >
                <RemoveCircleOutlineIcon />
              </IconButton>
            </Grid>
          </Grid>
        ))}

        <Button
          variant="outlined"
          startIcon={<AddCircleOutlineIcon />}
          onClick={handleAddAttribute}
        >
          Add Attribute
        </Button>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} variant="outlined" color="secondary" disabled={isLoading}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" color="primary" disabled={isLoading}>
          {isLoading ? <CircularProgress size={24} /> : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditMetadataModal;
