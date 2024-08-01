import Link from 'next/link';
import React, { useState, useEffect } from 'react';
import { SelectModel } from '@/lib/db';
import NERQuestions from './nlp-questions/ner-questions';
import SemanticSearchQuestions from './semantic-search-questions';

const RAGQuestions = ({
  models,
}: {
  models: SelectModel[];
}) => {

  console.log('All models:', models);

  // Begin state variables & func for source
  const [ifUseExistingSS, setUseExistingSS] = useState<string|null>(null);
  const [existingSSModelToUse, setExistingSSModelToUse] = useState<string|null>(null);
  const [existingSSmodels, setExistingSSmodels] = useState<SelectModel[]>([]);
  const [newSSModelCreated, setNewSSModelCreated] = useState<boolean>(false);

  useEffect(() => {
    setExistingSSmodels(models.filter(model => model.type === 'ndb'));
  }, [models]);

  console.log('Existing Semantic Search Models:', existingSSmodels);

  // End state variables & func for source

  // Begin state variables & func for LLM guardrail

  const [ifUseLGR, setIfUseLGR] = useState('');
  const [ifUseExistingLGR, setIfUseExistingLGR] = useState<string|null>(null);
  const [existingNERModels, setExistingNERModels] = useState<SelectModel[]>([]);
  const [existingNERModelToUse, setExistingNERModelToUse] = useState<string|null>(null);
  const [newNERModelCreated, setNewNERModelCreated] = useState<boolean>(false);

  useEffect(() => {
    setExistingNERModels(models.filter(model => model.type === 'ner model'));
  }, [models]);

  console.log('Existing NER Models:', existingNERModels);

  // End state variables & func for LLM guardrail

  const [modelName, setModelName] = useState('')

  // Begin state variables & func for LLM

  const [llmType, setLlmType] = useState<string|null>(null);

  // End state variables & func for LLM

  return (
    <div>
      {/* Begin Semantic Search Model */}

            <div className="mb-4">
              <span className="block text-lg font-semibold mb-2">Search Model</span>
              <label htmlFor="useExistingSemanticSearch" className="block text-sm font-medium text-gray-700">Use an existing semantic search model?</label>
              <select
                id="useExistingSemanticSearch"
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                value={ifUseExistingSS ? ifUseExistingSS : ''}
                onChange={(e) => setUseExistingSS(e.target.value)}
              >
                <option value="">-- Please choose an option --</option>
                <option value="Yes">Yes</option>
                <option value="No">No, create a new one</option>
              </select>
            </div>

            {/* Begin existing Semantic Search Models Dropdown */}

            {ifUseExistingSS === 'Yes' && (
              <div className="mb-4">
                <label htmlFor="semanticSearchModels" className="block text-sm font-medium text-gray-700">
                  Choose from existing semantic search model(s)
                </label>
                <select
                  id="semanticSearchModels"
                  className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                  value={existingSSModelToUse || ''}
                  onChange={(e) => setExistingSSModelToUse(e.target.value)}
                >
                  <option value="">-- Please choose a model --</option>
                  {existingSSmodels.map((model, index) => (
                    <option key={index} value={index}>
                      {`${model.model_name}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

              {/* End existing Semantic Search Models Dropdown */}

              {/* Begin Create new Semantic Search Model */}

      {
        ifUseExistingSS === 'No' &&
        <SemanticSearchQuestions/>
      }
              {/* End Create new Semantic Search Model */}

      {/* End Semantic Search Model */}




      {/* Begin choose LLM guardrail */}

            <span className="block text-lg font-semibold mb-2">LLM guardrail</span>
            <div className="mb-4">
              <label htmlFor="llmGuardrail" className="block text-sm font-medium text-gray-700">Would you like to add LLM guardrail?</label>
              <select
                id="llmGuardrail"
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                value={ifUseLGR}
                onChange={(e)=>setIfUseLGR(e.target.value)}
              >
                <option value="">-- Please choose an option --</option>
                <option value="Yes">Yes</option>
                <option value="No">No</option>
              </select>
            </div>

            {/* Begin choose to use existing LLM guardrail */}

            {ifUseLGR === 'Yes' && (
              <div className="mb-4">
                <label htmlFor="useExistingGuardrail" className="block text-sm font-medium text-gray-700">Use an existing NER model for LLM guardrail?</label>
                <select
                  id="useExistingGuardrail"
                  className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                  value={ifUseExistingLGR ? ifUseExistingLGR : ''}
                  onChange={(e) => setIfUseExistingLGR(e.target.value)}
                >
                  <option value="">-- Please choose an option --</option>
                  <option value="Yes">Yes</option>
                  <option value="No">No, create a new one</option>
                </select>
              </div>
            )}

            {/* End choose to use existing LLM guardrail */}

            {/* Begin creating a new NER model */}

            {ifUseLGR === 'Yes' && ifUseExistingLGR === 'No' && (
              <NERQuestions />
            )}

            {/* Begin creating a new NER model */}

            {/* Begin existing NER Models Dropdown */}
            {ifUseLGR === 'Yes' && ifUseExistingLGR === 'Yes' && (
              <div className="mb-4">
                <label htmlFor="nerModels" className="block text-sm font-medium text-gray-700">
                  Choose from existing NER Model(s)
                </label>
                <select
                  id="nerModels"
                  className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                  value={existingNERModelToUse || ''}
                  onChange={(e) => setExistingNERModelToUse(e.target.value)}
                >
                  <option value="">-- Please choose a model --</option>
                  {existingNERModels.map(model => (
                    <option key={model.id} value={model.id}>
                      {`${model.model_name}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* End existing NER Models Dropdown */}

      {/* End choose LLM guardrail */}



      {/* Begin chat interface */}
            <span className="block text-lg font-semibold mb-2">Chat</span>
            <div className="mb-4">
              <label htmlFor="llmType" className="block text-sm font-medium text-gray-700">Choose an LLM option</label>
              <select
                id="llmType"
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                value={llmType ? llmType : ''}
                onChange={(e) => setLlmType(e.target.value)}
              >
                <option value="">-- Please choose an option --</option>
                <option value="OpenAI">OpenAI</option>
                <option value="Llama">Llama</option>
                <option value="Self-host">Self-host</option>
              </select>
            </div>
      {/* End chat interface */}




      {/* Begin Model Name Input Field */}
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
      {/* End Model Name Input Field */}



      {/* Begin create and deploy */}
            {
              (existingSSModelToUse || newSSModelCreated) 
              && 
              (ifUseLGR === 'No' || (ifUseLGR === 'Yes' && (existingNERModelToUse || newNERModelCreated) )) 
              && 
              llmType 
              && 
              modelName 
              &&
              <div className="flex justify-center">
                <Link href="/">
                <button
                  type="button"
                  className="mb-4 bg-blue-500 text-white px-4 py-2 rounded-md"
                >
                  {`${ifUseExistingSS === 'No' || (ifUseLGR === 'Yes' && ifUseExistingLGR === 'No') ? 'Create' : 'Create and Deploy'}`}
                </button>
                </Link>
              </div>
            }
      {/* End create and deploy */}

    </div>
  );
};

export default RAGQuestions;
