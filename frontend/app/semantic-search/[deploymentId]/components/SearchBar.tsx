import React, { useCallback, useContext, useRef, useState, useEffect } from 'react';
import { Button } from '@mui/material';
import styled from 'styled-components';
import { borderRadius, color, duration, fontSizes, padding } from '../stylingConstants';
import { Spacer } from './Layout';
import { ModelService, Source } from '../modelServices';
import { ModelServiceContext } from '../Context';
import Sources from './Sources';
import useClickOutside from './hooks/useClickOutside';
import PromptToggle from './buttons/PromptToggle';
import SaveButton from './buttons/SaveButton';
import SearchTextInput from './SearchTextInput';
import Modal from './Modal';
import { Input } from '@/components/ui/input';
import { TextField } from '@mui/material';
import { DropdownMenu, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { fetchAutoCompleteQueries } from '@/lib/backend';
import { debounce } from 'lodash';

const Container = styled.section`
  box-shadow: 0 10px 10px 4px muted;
  width: 100%;
  display: flex;
  flex-direction: column;
  padding: 5px;
  padding-top: 10px;
`;

const SearchArea = styled.section`
  width: 100%;
  display: flex;
  flex-direction: row;
  align-items: center;
  height: fit-content;
`;

const Description = styled.section`
  font-size: ${fontSizes.s};
  color: ${color.subtext};
  display: flex;
  flex-direction: row;
  align-items: center;
`;

const TryNewModelButton = styled.button`
  border: 1px solid ${color.accent};
  border-radius: ${borderRadius.smallButton};
  transition-duration: ${duration.transition};
  font-size: ${fontSizes.s};
  font-weight: normal;
  color: ${color.accent};
  width: fit-content;
  padding: ${padding.smallButton};

  &:hover {
    background-color: ${color.accent};
    color: white;
    cursor: pointer;
  }

  &:active {
    background-color: ${color.accentDark};
  }
`;

const PanelContainer = styled.section`
  position: relative;
  height: 0;
  overflow-y: visible;
`;

const ButtonGroup = styled.div`
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
`;

interface ButtonProps {
  primary?: boolean;
}

const ErrorMessage = styled.p`
  color: red;
  font-size: 12px;
  margin-top: 5px;
`;

interface ModelDescriptionProps {
  onClickViewDocuments: () => void;
  sources: Source[];
  setSources: (sources: Source[]) => void;
  ifGenerationOn: boolean;
}

interface Suggestion {
  query: string;
  query_id: number;
}

function ModelDescription(props: ModelDescriptionProps) {
  return (
    <Description>
      {props.ifGenerationOn && `Generating answers from your documents`}
      <Spacer $width="7px" />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="contained" className="h-8 gap-1" onClick={props.onClickViewDocuments}>
            View Documents
          </Button>
        </DropdownMenuTrigger>
        <Sources sources={props.sources} setSources={props.setSources} visible />
      </DropdownMenu>
    </Description>
  );
}

function GlobalModelDescription() {
  return (
    <Description>
      Generating answers from knowledgebase documents, or
      <Spacer $width="7px" />
      <a href={typeof window !== 'undefined' ? window.location.origin : ''}>
        <TryNewModelButton>use your own documents</TryNewModelButton>
      </a>
    </Description>
  );
}

interface SearchBarProps {
  query: string;
  setQuery: (query: string) => void;
  onSubmit: (query: string, genaiPrompt: string) => void;
  sources: Source[];
  setSources: (sources: Source[]) => void;
  prompt: string;
  setPrompt: (prompt: string) => void;
  ifGenerationOn: boolean;
  cacheEnabled: boolean;

  abortController: AbortController | null;
  setAbortController: (controller: AbortController | null) => void;
  setAnswer: (answer: string) => void;

  modalOpen: boolean;
  setModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  showModelNameInput: boolean;
  setShowModelNameInput: React.Dispatch<React.SetStateAction<boolean>>;
  error: string;
  setError: React.Dispatch<React.SetStateAction<string>>;
}

export default function SearchBar({
  query,
  setQuery,
  onSubmit,
  sources,
  setSources,
  prompt,
  setPrompt,
  ifGenerationOn,
  cacheEnabled,

  abortController,
  setAbortController,
  setAnswer,

  modalOpen,
  setModalOpen,
  showModelNameInput,
  setShowModelNameInput,
  error,
  setError,
}: SearchBarProps) {
  const modelService = useContext<ModelService | null>(ModelServiceContext);
  const [showSources, setShowSources] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [modelName, setModelName] = useState('');

  const sourcesRef = useRef<HTMLElement>(null);
  const handleClickOutside = useCallback(() => {
    setShowSources(false);
  }, []);

  useClickOutside(sourcesRef, handleClickOutside);

  const handleSaveClick = () => {
    setModalOpen(true);
    setShowModelNameInput(false);
    setError('');
  };

  const handleShowModelNameInput = () => {
    setError(''); // Clear any previous errors
    setShowModelNameInput(true);
  };

  const handleBack = () => {
    setError(''); // Clear any previous errors
    setShowModelNameInput(false);
  };

  const handleOverride = () => {
    modelService!
      .saveModel(true)
      .then(() => {
        setModalOpen(false);
        setError('');
      })
      .catch((error) => {
        console.error('Error overriding model:', error);
        alert('Error overriding model:' + error);
        const errorMessage =
          typeof error === 'string' ? error : error.message || JSON.stringify(error);
        setError(errorMessage);
      });
  };

  const handleSaveAsNew = () => {
    if (modelName.trim() === '') {
      setError('Model name is required.');
      return;
    }

    modelService!
      .saveModel(false, modelName)
      .then(() => {
        setModalOpen(false);
        setError('');
      })
      .catch((error) => {
        console.error('Error overriding model:', error);
        alert('Error overriding model:' + error);
        const errorMessage =
          typeof error === 'string' ? error : error.message || JSON.stringify(error);
        setError(errorMessage);
      });
  };

  const handleSubmit = () => {
    // When a user hits enter (to trigger generation) or
    // click on one suggestion to trigger cache-generation, the suggestion bar would go away.
    setShowSuggestionBar(false);

    onSubmit(query, prompt);
  };

  const [showSuggestionBar, setShowSuggestionBar] = useState<boolean>(false);

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  const debouncedFetch = debounce((query) => {
    // Whether to show is default to true, but depends on if actual suggestions were fetched
    setShowSuggestionBar(suggestions && suggestions.length !== 0);

    const modelId = modelService?.getModelID();
    fetchAutoCompleteQueries(modelId!, query)
      .then((data) => {
        setSuggestions(data.suggestions); // Storing the suggestions in state
        console.log('suggestions:', data.suggestions); // Adjust according to actual data structure
        if (data.suggestions.length === 0) {
          setShowSuggestionBar(false); // don't show suggestion bar if 0 suggestions
        }
      })
      .catch((err) => console.error('Failed to fetch suggestions:', err));
  }, 300); // Adjust debounce time as needed

  useEffect(() => {
    if (!cacheEnabled) return;

    if (query.length > 2) {
      // Only fetch suggestions if query length is more than 2 characters
      debouncedFetch(query);
    } else {
      setSuggestions([]);
      setShowSuggestionBar(false); // don't show suggestion bar if 0 suggestions
    }
  }, [query, cacheEnabled]);

  return (
    <Container>
      <div>
        <SearchArea style={{ marginBottom: '5px' }}>
          <TextField
            autoFocus
            className="text-m w-full"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask anything..."
            style={{ height: '3rem' }}
            onSubmit={handleSubmit}
            onKeyDown={(e) => {
              if (e.keyCode === 13 && e.shiftKey === false) {
                e.preventDefault();
                handleSubmit();
              }
            }}
          />
          <Spacer $width="15px" />
          {/* <PromptToggle onClick={() => setDialogOpen((dialogOpen) => !dialogOpen)} /> */}
          <Spacer $width="7px" />
        </SearchArea>
        <div className="w-full mt-2" style={{ backgroundColor: 'white' }}>
          {cacheEnabled &&
            showSuggestionBar &&
            suggestions.slice(0, 3).map((suggestion) => (
              <button
                key={suggestion.query_id}
                onClick={() => {
                  // When a user hits enter (to trigger generation) or
                  // click on one suggestion to trigger cache-generation, the suggestion bar would go away.
                  setSuggestions([]); // this part prevents setShowSuggestionBar(suggestions && suggestions.length !== 0) to be true, thus suggestions won't show up.
                  setShowSuggestionBar(false);

                  const suggestionQuery = suggestion.query;
                  setQuery(suggestionQuery);
                  onSubmit(suggestionQuery, prompt);
                }}
                className="block w-full text-left p-2 hover:bg-gray-100 cursor-pointer"
              >
                {suggestion.query}
              </button>
            ))}
        </div>
      </div>
      {dialogOpen && (
        <>
          <Spacer $height="5px" />
          <SearchTextInput
            placeholder="Enter custom prompt"
            onSubmit={() => onSubmit(query, prompt)}
            value={prompt}
            setValue={setPrompt}
          />
        </>
      )}

      <Spacer $height="5px" />
      {!showSuggestionBar && (
        <ModelDescription
          onClickViewDocuments={() => setShowSources((val) => !val)}
          sources={sources}
          setSources={setSources}
          ifGenerationOn={ifGenerationOn}
        />
      )}
      <Spacer $height="5px" />

      {modalOpen && (
        <Modal onClose={() => setModalOpen(false)}>
          <h2>Save Model</h2>
          <p>Do you want to override the existing model or save as a new model?</p>
          {!showModelNameInput ? (
            <>
              {error && <ErrorMessage>{error}</ErrorMessage>}
              <ButtonGroup>
                <Button onClick={handleOverride} variant="contained">
                  Override
                </Button>
                <Button onClick={handleShowModelNameInput} variant="contained">
                  Save as New
                </Button>
              </ButtonGroup>
            </>
          ) : (
            <>
              <Input
                type="text"
                placeholder="Enter model name"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
              />
              {error && <ErrorMessage>{error}</ErrorMessage>}
              <ButtonGroup>
                <Button onClick={handleBack} variant="contained" color="error">
                  Back
                </Button>
                <Button onClick={handleSaveAsNew} variant="contained">
                  Submit
                </Button>
              </ButtonGroup>
            </>
          )}
        </Modal>
      )}
    </Container>
  );
}
