"use client"

import { useState, useEffect } from 'react';
import { SelectModel } from '@/lib/db';
import RAGQuestions from './rag-questions';
import NLPQuestions from './nlp-questions/nlp-questions';
import SemanticSearchQuestions from './semantic-search-questions';
import { fetchPublicModels, fetchPrivateModels, fetchPendingModels } from "@/lib/backend"

export default function ChooseProblem() {
  const [modelType, setModelType] = useState('');

  const [privateModels, setPrivateModels] = useState<SelectModel[]>([])
  const [pendingModels, setPendingModels] = useState<SelectModel[]>([]);

  useEffect(() => {
    async function getModels() {
        try {
          let response = await fetchPublicModels('');
          const publicModels = response.data;
          console.log('publicModels', publicModels)

          response = await fetchPrivateModels('');
          const privateModels: SelectModel[] = response.data;
          setPrivateModels(privateModels)

          response = await fetchPendingModels();
          const pendingModels = response.data; // Extract the data field
          console.log('pendingModels', pendingModels)

        } catch (err) {
          if (err instanceof Error) {
              console.log(err.message);
          } else {
              console.log('An unknown error occurred');
          }
      }
    }

    getModels();
  }, []);

  return (
    <>
        <span className="block text-lg font-semibold mb-2">Use case</span>
        <div className="mb-4">
          <label htmlFor="modelType" className="block text-sm font-medium text-gray-700">Please select the model type based on your use case:</label>
          <select
            id="modelType"
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
            value={modelType}
            onChange={(e)=>setModelType(e.target.value)}
          >
            <option value="">-- Please choose an option --</option>
            <option value="semantic-search">Semantic search</option>
            <option value="NLP">NLP (Natural Language Processing)</option>
            <option value="RAG">RAG (Retrieval Augmented Generation)</option>
          </select>
        </div>

        {modelType && (
          <div>
            {modelType === 'RAG' && <RAGQuestions models = {privateModels}/>}
            {modelType === 'NLP' && <NLPQuestions />}
            {modelType === 'semantic-search' && <SemanticSearchQuestions />}
          </div>
        )}
    </>
  );
}
