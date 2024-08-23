import React, { useState } from "react";
import styled from "styled-components";

type Props = {
    isOpen: boolean;
    handleCloseModal: () => void;
    addSources: (
        selectedFiles: FileList | null,
        s3Urls: string[],
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
    const [s3Urls, setS3Urls] = useState<string[]>([""]);

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSelectedFiles(event.target.files);
    };

    const handleS3UrlChange = (
        index: number,
        event: React.ChangeEvent<HTMLInputElement>,
    ) => {
        const newS3Urls = [...s3Urls];
        newS3Urls[index] = event.target.value;
        setS3Urls(newS3Urls);
    };

    const handleAddS3Url = () => {
        setS3Urls([...s3Urls, ""]);
    };

    const handleRemoveS3Url = (index: number) => {
        const newS3Urls = s3Urls.filter((_, i) => i !== index);
        setS3Urls(newS3Urls);
    };

    const handleUpload = async () => {
        if (selectedFiles || s3Urls.some((url) => url.trim() !== "")) {
            setUploading(true);
            try {
                await addSources(
                    selectedFiles,
                    s3Urls.filter((url) => url.trim() !== ""),
                );
            } catch (error) {
                console.error("Upload error:", error);
                alert(
                    `Upload failed due to error ${error}. Please try again.`
                );
            }
            setUploading(false);
            setSelectedFiles(null);
            setS3Urls([""]);
            handleCloseModal();
            refreshSources();
        }
    };

    const handleModalClick = (
        event: React.MouseEvent<HTMLDivElement, MouseEvent>,
    ) => {
        event.stopPropagation();
    };

    if (!isOpen) {
        return null;
    }

    const isUploadDisabled =
        ((!selectedFiles || selectedFiles.length === 0) &&
            s3Urls.every((url) => url.trim() === "")) ||
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
                <p>Or add S3 URLs:</p>
                {s3Urls.map((url, index) => (
                    <div
                        key={index}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            marginBottom: "10px",
                        }}
                    >
                        <input
                            type="text"
                            placeholder={`S3 URL ${index + 1}`}
                            value={url}
                            onChange={(e) => handleS3UrlChange(index, e)}
                            style={{ flex: 1, marginRight: "10px" }}
                        />
                        <button onClick={() => handleRemoveS3Url(index)}>
                            Remove
                        </button>
                    </div>
                ))}
                <ButtonContainer>
                    <button
                        onClick={handleAddS3Url}
                        style={{ marginRight: "10px" }}
                    >
                        Add More
                    </button>
                </ButtonContainer>
                <ButtonContainer>
                    <UploadButton
                        onClick={handleUpload}
                        disabled={isUploadDisabled}
                    >
                        {uploading
                            ? "Adding files to model..."
                            : "Upload Files"}
                    </UploadButton>
                </ButtonContainer>
            </Modal>
        </Overlay>
    );
};

export default FileUploadModal;
