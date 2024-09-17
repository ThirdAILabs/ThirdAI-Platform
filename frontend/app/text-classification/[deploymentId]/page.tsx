'use client';

import { useEffect, useState } from 'react';
import { Container, TextField, Box } from '@mui/material';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import * as _ from 'lodash';
import { useTextClassificationEndpoints } from '@/lib/backend';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';

export default function Page() {
  const { workflowName, predict } = useTextClassificationEndpoints();
  const [inputText, setInputText] = useState('');
  const [predictions, setPredictions] = useState<[string, number][]>([]);

  const handleRun = () => {
    if (inputText === '') {
      return;
    }
    predict(inputText).then((result) => {
      setPredictions(
        result.predicted_classes.map(([name, score]) => [name, Math.floor(score * 100)])
      );
    });
  };

  return (
    <div
      className="bg-muted"
      style={{ width: '100%', display: 'flex', justifyContent: 'center', height: '100vh' }}
    >
      <Tabs defaultValue="interact" style={{ width: '100%' }}>
        <div style={{ position: 'fixed', top: '20px', left: '20px' }}>
          <div className="text-muted-foreground" style={{ fontSize: '16px' }}>
            Text Classification
          </div>
          <div style={{ fontWeight: 'bold', fontSize: '24px' }}>{workflowName}</div>
        </div>
        <Container
          style={{
            textAlign: 'center',
            paddingTop: '20vh',
            width: '70%',
            minWidth: '400px',
            maxWidth: '800px',
          }}
        >
          <Box display="flex" justifyContent="center" alignItems="center" width="100%">
            <Input
              autoFocus
              className="text-md"
              style={{ height: '3rem' }}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Enter your text..."
              onSubmit={handleRun}
              onKeyDown={(e) => {
                if (e.keyCode === 13 && e.shiftKey === false) {
                  e.preventDefault();
                  handleRun();
                }
              }}
            />
            <Button
              size="sm"
              style={{ height: '3rem', marginLeft: '10px', padding: '0 20px' }}
              onClick={handleRun}
            >
              Run
            </Button>
          </Box>
          <Box mt={4}>
            {predictions.map((prediction, index) => (
              <Card
                key={index}
                style={{
                  marginTop: '10px',
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'row',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <CardHeader>
                  <div className="d-flex flex-column justify-content-start">
                    <p className="text-muted-foreground d-flex flex-row text-left">class</p>
                    <CardTitle>{prediction[0]}</CardTitle>
                  </div>
                </CardHeader>
                <div
                  className="bg-muted"
                  style={{
                    display: 'flex',
                    aspectRatio: 1,
                    margin: '12px',
                    justifyContent: 'center',
                    alignItems: 'center',
                    borderRadius: '5px',
                    cursor: 'default',
                    flexDirection: 'column',
                    padding: '5px 10px 10px 10px',
                  }}
                >
                  <p className="text-muted-foreground">score</p>
                  <CardTitle>{prediction[1]}</CardTitle>
                </div>
              </Card>
            ))}
          </Box>
        </Container>
      </Tabs>
    </div>
  );
}
