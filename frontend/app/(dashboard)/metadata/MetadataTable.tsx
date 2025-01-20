// /app/metadata/MetadataTable.tsx
'use client';

import React, { useState } from 'react';
import {
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Paper,
  IconButton,
  Typography,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import EditMetadataModal from './EditMetadataModal';
import { DocumentMetadata, MetadataAttribute, sampleDocuments } from './sampleData';

const MetadataTable: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentMetadata[]>(sampleDocuments);
  const [selectedDocument, setSelectedDocument] = useState<DocumentMetadata | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const handleEdit = (document: DocumentMetadata) => {
    setSelectedDocument(document);
    setIsModalOpen(true);
  };

  const handleUpdate = (documentId: string, updatedAttributes: MetadataAttribute[]) => {
    const updatedDocuments = documents.map((doc) =>
      doc.document_id === documentId ? { ...doc, metadata_attributes: updatedAttributes } : doc
    );
    setDocuments(updatedDocuments);
    setIsModalOpen(false);
    setSelectedDocument(null);
  };

  return (
    <>
      <TableContainer component={Paper}>
        <Table aria-label="metadata table">
          <TableHead>
            <TableRow>
              <TableCell>
                <strong>Document Name</strong>
              </TableCell>
              <TableCell>
                <strong>Metadata Attributes</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Actions</strong>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {documents.map((doc) => (
              <TableRow key={doc.document_id}>
                <TableCell component="th" scope="row">
                  {doc.document_name}
                </TableCell>
                <TableCell>
                  <ul className="list-disc pl-5">
                    {doc.metadata_attributes.map((attr, index) => (
                      <li key={index}>
                        <Typography variant="body2" component="span" fontWeight="bold">
                          {attr.attribute_name}:
                        </Typography>{' '}
                        {attr.value}
                      </li>
                    ))}
                  </ul>
                </TableCell>
                <TableCell align="center">
                  <IconButton
                    color="primary"
                    aria-label={`edit metadata for ${doc.document_name}`}
                    onClick={() => handleEdit(doc)}
                  >
                    <EditIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Edit Metadata Modal */}
      {isModalOpen && selectedDocument && (
        <EditMetadataModal
          document={selectedDocument}
          onClose={() => setIsModalOpen(false)}
          onSave={(updatedAttributes) =>
            handleUpdate(selectedDocument.document_id, updatedAttributes)
          }
        />
      )}
    </>
  );
};

export default MetadataTable;
