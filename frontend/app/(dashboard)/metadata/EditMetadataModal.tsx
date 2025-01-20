// /app/metadata/EditMetadataModal.tsx
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
  Typography,
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import { DocumentMetadata, MetadataAttribute } from './sampleData';

interface EditMetadataModalProps {
  document: DocumentMetadata;
  onClose: () => void;
  onSave: (updatedAttributes: MetadataAttribute[]) => void;
}

const EditMetadataModal: React.FC<EditMetadataModalProps> = ({ document, onClose, onSave }) => {
  const [attributes, setAttributes] = useState<MetadataAttribute[]>(document.metadata_attributes);

  const handleChange = (index: number, field: keyof MetadataAttribute, value: string) => {
    const updated = [...attributes];
    updated[index] = { ...updated[index], [field]: value };
    setAttributes(updated);
  };

  const handleAddAttribute = () => {
    setAttributes([...attributes, { attribute_name: '', description: '', value: '' }]);
  };

  const handleRemoveAttribute = (index: number) => {
    const updated = [...attributes];
    updated.splice(index, 1);
    setAttributes(updated);
  };

  const handleSubmit = () => {
    // Validation: Ensure all fields are filled
    for (const attr of attributes) {
      if (!attr.attribute_name.trim() || !attr.value.trim()) {
        alert('Attribute Name and Value cannot be empty.');
        return;
      }
    }
    onSave(attributes);
  };

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Edit Metadata for {document.document_name}</DialogTitle>
      <DialogContent dividers>
        {attributes.map((attr, index) => (
          <Grid
            container
            spacing={2}
            key={index}
            alignItems="center"
            style={{ marginBottom: '16px' }}
          >
            <Grid item xs={12} sm={4}>
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
                label="Description"
                value={attr.description}
                onChange={(e) => handleChange(index, 'description', e.target.value)}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12} sm={3}>
              <TextField
                label="Value"
                value={attr.value}
                onChange={(e) => handleChange(index, 'value', e.target.value)}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12} sm={12}>
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
        <Button onClick={onClose} variant="outlined" color="secondary">
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" color="primary">
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditMetadataModal;
