import React, { useState } from 'react';
import styled from 'styled-components';

type Props = {
  isOpen: boolean;
  handleCloseModal: () => void;
  addSources: (
    selectedFiles: FileList | null,
    cloudUrls: { type: 's3' | 'azure' | 'gcp'; url: string }[]
  ) => Promise<any>;
  refreshSources: () => void;
};

const Overlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
`;

const Modal = styled.div`
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  position: relative;
`;

const CloseButton = styled.div`
  position: absolute;
  top: 10px;
  right: 10px;
  cursor: pointer;
  font-weight: bold;
`;

const ButtonContainer = styled.div`
  display: flex;
  justify-content: center;
  margin-top: 20px;
`;

const UploadButton = styled.button`
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background-color: #007bff;
  color: white;

  &:disabled {
    background-color: #aaa;
    cursor: not-allowed;
  }
`;

const FileUploadModal: React.FC<Props> = ({
  isOpen,
  handleCloseModal,
  addSources,
  refreshSources,
}) => {
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [cloudUrls, setCloudUrls] = useState<{ type: 's3' | 'azure' | 'gcp'; url: string }[]>([
    { type: 's3', url: '' },
  ]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(event.target.files);
  };

  const handleCloudUrlChange = (index: number, field: 'type' | 'url', value: string) => {
    const newCloudUrls = [...cloudUrls];
    newCloudUrls[index] = { ...newCloudUrls[index], [field]: value };
    setCloudUrls(newCloudUrls);
  };

  const handleAddCloudUrl = () => {
    setCloudUrls([...cloudUrls, { type: 's3', url: '' }]);
  };

  const handleRemoveCloudUrl = (index: number) => {
    const newCloudUrls = cloudUrls.filter((_, i) => i !== index);
    setCloudUrls(newCloudUrls);
  };

  const handleUpload = async () => {
    const validCloudUrls = cloudUrls.filter((entry) => entry.url.trim() !== '');
    if (selectedFiles || validCloudUrls.length > 0) {
      setUploading(true);
      try {
        await addSources(selectedFiles, validCloudUrls);
        setSelectedFiles(null);
        setCloudUrls([{ type: 's3', url: '' }]);
        handleCloseModal();
        refreshSources();
      } catch (error) {
        console.error('Upload error:', error);
        alert(`Upload failed due to error ${error}. Please try again.`);
      } finally {
        setUploading(false);
      }
    }
  };

  const handleModalClick = (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    event.stopPropagation();
  };

  if (!isOpen) {
    return null;
  }

  const isUploadDisabled =
    ((!selectedFiles || selectedFiles.length === 0) &&
      cloudUrls.every((entry) => entry.url.trim() === '')) ||
    uploading;

  return (
    <Overlay onClick={handleCloseModal}>
      <Modal onClick={handleModalClick}>
        <CloseButton onClick={handleCloseModal}>X</CloseButton>
        <p>Select files to upload:</p>
        <input
          type="file"
          multiple
          onChange={handleChange}
          accept=".pdf,.csv,.docx,.txt,.pptx,.eml"
        />

        <p>Or add Cloud URLs:</p>
        {cloudUrls.map((entry, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              alignItems: 'center',
              marginBottom: '10px',
            }}
          >
            <select
              value={entry.type}
              onChange={(e) => handleCloudUrlChange(index, 'type', e.target.value)}
              style={{ marginRight: '10px' }}
            >
              <option value="s3">S3</option>
              <option value="azure">Azure</option>
              <option value="gcp">GCP</option>
            </select>
            <input
              type="text"
              placeholder="Cloud URL"
              value={entry.url}
              onChange={(e) => handleCloudUrlChange(index, 'url', e.target.value)}
              style={{ flex: 1, marginRight: '10px' }}
            />
            <button onClick={() => handleRemoveCloudUrl(index)}>Remove</button>
          </div>
        ))}
        <ButtonContainer>
          <button onClick={handleAddCloudUrl} style={{ marginRight: '10px' }}>
            Add More URLs
          </button>
        </ButtonContainer>

        <ButtonContainer>
          <UploadButton onClick={handleUpload} disabled={isUploadDisabled}>
            {uploading ? 'Adding files to model...' : 'Upload Files'}
          </UploadButton>
        </ButtonContainer>
      </Modal>
    </Overlay>
  );
};

export default FileUploadModal;
