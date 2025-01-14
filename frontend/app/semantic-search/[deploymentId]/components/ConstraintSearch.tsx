import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { ModelService, Source } from '../modelServices';
import { ModelServiceContext } from '../Context';
import { Button, Dialog, DialogTitle, DialogContent, Divider } from '@mui/material';
import SelectDocument from './SelectDocument';
import Sources from './Sources';
import MetadataRenderer from './MetaDataRenderer';

interface MeatadataFeedbackProps {
  [key: string]: { [key: string]: [] };
}

const ConstraintSearch = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const modelService = useContext<ModelService | null>(ModelServiceContext);
  const [metaData, setMetadata] = useState<{ [key: string]: any }>();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const getSources = async () => {
    if (modelService) {
      const data = await modelService.sources();
      setSources(data);
    }
  };

  const getMetadata = async () => {
    const thisMetadata: { [key: string]: any } = {};
    if (sources && modelService) {
      for (let index = 0; index < sources.length; index++) {
        const source = sources[index];
        const thisDocMetaData = await modelService.fetchMetaData(source.source_id, source.version);
        thisMetadata[source.source_id] = thisDocMetaData;
      }
    }
    setMetadata(thisMetadata);
  };

  useEffect(() => {
    getSources();
  }, []);

  useEffect(() => {
    getMetadata();
  }, [sources]);

  const [selectedSource, setSelectedSource] = useState<Source | null>(null);

  const handleSelectedSource = (source: Source) => {
    if (!selectedSource) {
      setSelectedSource(source);
      setIsDialogOpen(true); // Open dialog when a source is selected
    } else {
      setSelectedSource(null);
    }
  };

  const handleDialogClose = () => {
    setIsDialogOpen(false); // Close dialog when clicking outside or the close action
    setSelectedSource(null); // Reset selected source
  };
  const [metadataFeedback, setMetadataFeedback] = useState<MeatadataFeedbackProps>();
  const handleSubmit = (props: { [key: string]: [] }) => {
    if (selectedSource) {
      setMetadataFeedback((prev: any) => ({
        ...prev,
        [selectedSource.source_id]: props,
      }));
      handleDialogClose();
    }
  };
  console.log('metadataFeedback: ', metadataFeedback);
  return (
    <>
      <div className="gap-4">
        <SelectDocument sources={sources} handleSelectedSource={handleSelectedSource} />

        {/* Pop-up for MetadataRenderer */}
        <Dialog open={isDialogOpen} onClose={handleDialogClose} maxWidth="sm" fullWidth>
          <DialogTitle>Select filters to refine your search</DialogTitle>
          <Divider className="mb-5" />
          <DialogContent>
            {selectedSource && metaData && (
              <MetadataRenderer
                metadata={metaData[selectedSource.source_id]}
                handleSubmit={handleSubmit}
              />
            )}
          </DialogContent>
        </Dialog>
      </div>
    </>
  );
};

export default ConstraintSearch;
