import Link from 'next/link';
import React, { useState } from 'react';
import { SelectModel } from '@/lib/db';
import { train_ndb } from '@/lib/backend';

interface SemanticSearchQuestionsProps {
  onCreateModel?: (userName: string, modelName: string) => void;
  stayOnPage?: boolean;
};

const SemanticSearchQuestions = ({ onCreateModel, stayOnPage }: SemanticSearchQuestionsProps) => {
    // Begin state variables & func for source
    const [sources, setSources] = useState<Array<{ type: string, value: File | null }>>([]);
    const [newSourceType, setNewSourceType] = useState<string>('');
    const [newSourceValue, setNewSourceValue] = useState<File | null>(null);
  
    const handleAddSource = () => {
      if (newSourceType && newSourceValue) {
        setSources([...sources, { type: newSourceType, value: newSourceValue }]);
        setNewSourceType('');
        setNewSourceValue(null);
      }
    };
  
    const handleSourceTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      setNewSourceType(e.target.value);
    };
  
    const handleSourceValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
        setNewSourceValue(e.target.files[0]);
      }
    };
  
    const handleDeleteSource = (index: number) => {
      const updatedSources = sources.filter((_, i) => i !== index);
      setSources(updatedSources);
    };


    const [isLoading, setIsLoading] = useState(false);
    const [modelName, setModelName] = useState('')
    const [retriever, setRetriever] = useState('finetunable_retriever');

    const handleFileFormdata = async () => {
      let formData = new FormData();
      const fileDetailsList: Array<{ mode: string; location: string }> = [];

      sources.forEach((source) => {
        if (source.type === 'local' && source.value) {
          formData.append('files', source.value);
          fileDetailsList.push({ mode: 'unsupervised', location: 'local' });
        } else if (source.type === 's3' && source.value) {
          formData.append('files', new File([], source.value.name)); // "don't care" as a placeholder
          fileDetailsList.push({ mode: 'unsupervised', location: 's3' });
        }
      });
  
      const extraOptionsForm = { retriever };
      formData.append('extra_options_form', JSON.stringify(extraOptionsForm));
      formData.append('file_details_list', JSON.stringify({ file_details: fileDetailsList }));

      return formData;
    };

    const handleSubmit = async () => {
      setIsLoading(true);
      try {
        if (onCreateModel) {
          onCreateModel('peter', modelName);
        }

        const formData = await handleFileFormdata();

        // Print out all the FormData entries
        formData.forEach((value, key) => {
          console.log(`${key}:`, value);
        });

        console.log('modelName', modelName)

        await train_ndb({ name: modelName, formData });
      } catch (error) {
        console.log(error);
      } finally {
        setIsLoading(false);
      }
    };

    const createButton = (
      <button
        type="button"
        className="mb-4 bg-blue-500 text-white px-4 py-2 rounded-md"
        onClick={handleSubmit}
      >
        Create
      </button>
    );

    return (
      <div>
        {
          <>
            <span className="block text-lg font-semibold mb-2">Choose source files</span>
            <p className="mb-4">Please upload the necessary files.</p>

            <div className="mb-4">
              <label htmlFor="newSourceType" className="block text-sm font-medium text-gray-700">Select Source Type</label>
              <select
                id="newSourceType"
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                value={newSourceType}
                onChange={handleSourceTypeChange}
              >
                <option value="">-- Please choose an option --</option>
                <option value="s3">S3</option>
                <option value="local">Local File</option>
              </select>
            </div>

            {newSourceType === 's3' && (
              <div className="mb-4">
                <label htmlFor="newSourceValue" className="block text-sm font-medium text-gray-700">S3 URL</label>
                <input
                  type="text"
                  id="newSourceValue"
                  className="mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="Enter S3 URL"
                  onChange={(e) => setNewSourceValue(new File([], e.target.value))} // "don't care" as a placeholder
                />
              </div>
            )}

            {newSourceType === 'local' && (
              <div className="mb-4">
                <label htmlFor="newSourceValue" className="block text-sm font-medium text-gray-700">Upload File</label>
                <input
                  type="file"
                  id="newSourceValue"
                  className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                  onChange={handleSourceValueChange}
                  multiple
                />
              </div>
            )}

            <button
              type="button"
              className="mb-4 bg-blue-500 text-white px-4 py-2 rounded-md"
              onClick={handleAddSource}
            >
              Add Source
            </button>

            {/* Begin Display added sources */}
            <div>
              <h3 className="text-lg font-semibold mb-2">Added Sources</h3>
              <ul>
                {sources.map((source, index) => (
                  <li key={index} className="mb-2 flex items-center justify-between">
                    <span className="inline-block px-4 py-2 rounded-md bg-gray-200 text-black">
                      <strong>{source.type === 's3' ? 'S3 URL' : 'Local File'}:</strong> {source.value?.name || 'N/A'}
                    </span>
                    <button
                      type="button"
                      className="ml-4 bg-red-500 text-white px-2 py-1 rounded-md"
                      onClick={() => handleDeleteSource(index)}
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            {/* End Display added sources */}
          </>
        }
        {/* End source files */}

        {/* Add Model Name Input Field */}
        <span className="block text-lg font-semibold mb-2">Name your model</span>
        <div className="mb-4">
          <label htmlFor="modelName" className="block text-sm font-medium text-gray-700">
            Model Name
          </label>
          <input
            type="text"
            id="modelName"
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
            value={modelName || ''}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="Enter model name"
          />
        </div>

        <div className="flex justify-center">
          {
            stayOnPage ? createButton : <Link href="/"> {createButton} </Link>
          }
        </div>
      </div>
    );
};

export default SemanticSearchQuestions;
