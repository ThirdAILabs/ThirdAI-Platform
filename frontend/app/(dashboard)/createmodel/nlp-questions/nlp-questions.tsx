// app/NLPQuestions.js
import React, { useState } from 'react';
import NERQuestions from './ner-questions';
import SCQQuestions from './sentence-classification-questions'
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { CardDescription } from '@/components/ui/card';
import { Divider } from '@mui/material';

const NLPQuestions = () => {
  const [question, setQuestion] = useState('');
  const [loadingAnswer, setLoadingAnswer] = useState<boolean>(false);
  const [answer, setAnswer] = useState('');
  const [confirmedAnswer, setConfirmedAnswer] = useState<boolean>(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuestion(e.target.value);
  };

  const submit = async () => {
    if (!question) {
      console.error('Question is not valid');
      return;
    }
    if (loadingAnswer) {
      return;
    }

    setLoadingAnswer(true);

    try {
      const response = await fetch('/api/which-nlp-use-case', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question }),
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const result = await response.json();
      setAnswer(result.answer);
    } catch (error) {
      console.error('Error during fetch:', error);
    } finally {
      setLoadingAnswer(false);
    }
  };

  return (
    <div style={{ width: "100%" }}>
      {
        !confirmedAnswer && !answer && <>
          <span className="block text-lg font-semibold">NLP task assistant</span>
          <CardDescription>Say &quot;I want to analyze my customers&apos; reviews&quot;</CardDescription>
          <CardDescription>or &quot;I want to analyze the individual tokens within a report document&quot;</CardDescription>
          <div style={{ display: "flex", flexDirection: "row", gap: "20px", justifyContent: "space-between", margin: "20px 0" }}>
            <Input
              className="text-md"
              value={question}
              onChange={handleInputChange}
              placeholder="Describe your use case..."
              onKeyDown={(e) => {
                if (e.keyCode === 13 && e.shiftKey === false) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
          </div>
          <Button onClick={submit} variant={loadingAnswer ? "secondary" : "default"} style={{ width: "100%" }}>{loadingAnswer ? "Understanding your use case..." : "Submit"}</Button>
        </>
      }
      {
        !confirmedAnswer && answer && <div style={{ marginTop: "20px" }}>
          <span className="block text-lg font-semibold" style={{ marginBottom: "10px" }}>Our recommendation</span>
          <CardDescription>{answer}</CardDescription>
          <div style={{ width: "100%", marginTop: "20px", display: "flex", flexDirection: "row", justifyContent: "space-between", gap: "10px" }}>
            <Button
              style={{ width: "100%" }}
              variant="outline"
              onClick={() => setAnswer('')}>
              Retry
            </Button>
            <Button
              style={{ width: "100%" }}
              onClick={() => setConfirmedAnswer(true)}>
              Continue
            </Button>
          </div>
        </div>
      }
      {
        confirmedAnswer && answer && (
          answer.includes('Sentence classification') ? (
            <SCQQuestions question={question} answer={answer} />
          ) : answer.includes('Token classification') ? (
            <NERQuestions />
          ) : null
        )
      }
    </div>
  );
};

export default NLPQuestions;
