"use client"

import { useState, useEffect } from 'react';
import { SelectModel } from '@/lib/db';
import RAGQuestions from './rag-questions';
import NLPQuestions from './nlp-questions/nlp-questions';
import SemanticSearchQuestions from './semantic-search-questions';
import { fetchPublicModels, fetchPrivateModels, fetchPendingModels } from "@/lib/backend"
import { Button } from '@/components/ui/button';
import { Divider } from '@mui/material';
import { CardDescription } from '@/components/ui/card';

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

  const RETRIEVAL = "Retrieval"
  const NLP = "Natural Language Processing"
  const RAG = "Retrieval Augmented Generation"

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span className="block text-lg font-semibold">Use case</span>
        <CardDescription>Please select the app type based on your use case.</CardDescription>
        <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
          {
            [RETRIEVAL, NLP, RAG].map((type, index) => {
              const variant = (
                !modelType
                  ? "default"
                  : modelType === type
                    ? "secondary"
                    : "outline"
              );
              return <Button
                key={index}
                onClick={() => setModelType(type)}
                variant={variant}
                style={{ width: "100%", ...(variant === "outline" ? {} : { border: "1px solid white" }) }}
              >
                {type}
              </Button>
            })
          }
        </div>

        {modelType && (
          <div style={{ width: "100%", marginTop: "20px" }}>
            <Divider style={{ marginBottom: "20px" }} />
            {modelType === RAG && <RAGQuestions models={privateModels} />}
            {modelType === NLP && <NLPQuestions />}
            {modelType === RETRIEVAL && <SemanticSearchQuestions />}
          </div>
        )}
      </div>

    </>
  );
}
