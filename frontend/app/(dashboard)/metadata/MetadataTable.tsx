'use client';

import React, { useState, useEffect } from 'react';
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
  CircularProgress,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import EditMetadataModal from './EditMetadataModal';
import {
  getDocumentMetadata,
  getWorkflowDetails,
  deploymentBaseUrl,
  getSources,
} from '@/lib/backend';
import { useSearchParams } from 'next/navigation';

interface MetadataAttribute {
  attribute_name: string;
  value: string | number;
}

interface DocumentMetadata {
  document_id: string;
  document_name: string;
  metadata_attributes: MetadataAttribute[];
}

const MetadataTable: React.FC = () => {
  const searchParams = useSearchParams();
  const workflowId = searchParams.get('workflow_id');
  const username = searchParams.get('username');

  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentMetadata | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deploymentUrl, setDeploymentUrl] = useState<string>('');

  useEffect(() => {
    const fetchMetadata = async () => {
      if (!workflowId) return;

      try {
        // First get the workflow details to get the dependencies
        const workflowDetails = await getWorkflowDetails(workflowId);

        if (workflowDetails.data.type !== 'enterprise-search') {
          throw new Error('This workflow is not an enterprise-search type');
        }

        // Get the deployment URL using the first dependency for enterprise-search
        const firstDependency = workflowDetails.data.dependencies?.[0];
        if (!firstDependency?.model_id) {
          throw new Error('No dependency model found');
        }
        const deploymentUrl = `${deploymentBaseUrl}/${firstDependency.model_id}`;
        setDeploymentUrl(deploymentUrl); // Add this line
        console.log('Deployment URL:', deploymentUrl);

        // Fetch sources
        const sources = await getSources(deploymentUrl);
        console.log('Sources:', sources);

        if (sources.length === 0) {
          throw new Error('No sources found for this model');
        }

        // Fetch metadata for each source
        const documentsData = await Promise.all(
          sources.map(async (source) => {
            try {
              const metadataResponse = await getDocumentMetadata(deploymentUrl, source.source_id);

              // Extract filename from the full path
              const fileName = source.source.split('/').pop() || source.source;

              // Transform the metadata into our document format
              const metadataEntries = Object.entries(metadataResponse.data).map(([key, value]) => ({
                attribute_name: key,
                value: value,
              }));

              return {
                document_id: source.source_id,
                document_name: fileName,
                metadata_attributes: metadataEntries,
              };
            } catch (err) {
              console.error(`Error fetching metadata for source ${source.source_id}:`, err);
              return null;
            }
          })
        );

        // Filter out any failed metadata fetches and set the documents
        const validDocuments = documentsData.filter((doc): doc is DocumentMetadata => doc !== null);
        setDocuments(validDocuments);
      } catch (err) {
        console.error('Error fetching metadata:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch metadata');
      } finally {
        setIsLoading(false);
      }
    };

    fetchMetadata();
  }, [workflowId]);

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

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <CircularProgress />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-500 text-center p-4">
        <Typography variant="h6">Error: {error}</Typography>
      </div>
    );
  }

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

      {isModalOpen && selectedDocument && deploymentUrl && (
        <EditMetadataModal
          document={selectedDocument}
          deploymentUrl={deploymentUrl}
          onClose={() => setIsModalOpen(false)}
          onSave={(documentId, updatedAttributes) => handleUpdate(documentId, updatedAttributes)}
        />
      )}
    </>
  );
};

export default MetadataTable;
