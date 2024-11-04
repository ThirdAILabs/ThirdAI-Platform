'use client';

import { useState, useRef } from 'react';
import { Container, Box, CircularProgress, Typography, Alert } from '@mui/material';
import { Tabs } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import * as _ from 'lodash';
import { useTextClassificationEndpoints } from '@/lib/backend';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { parseCSV, parseExcel, parseTXT } from '@/utils/fileParsingUtils';

interface ParsedData {
  type: 'csv' | 'pdf' | 'other';
  content: string;
  rows?: { label: string; content: string }[];
  pdfParagraphs?: string[];
}

export default function Page() {
  const { workflowName, predict, getTextFromFile } = useTextClassificationEndpoints();
  const [inputText, setInputText] = useState('');
  const [predictions, setPredictions] = useState<[string, number][]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<ParsedData | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_FILE_SIZE = 1024 * 1024; // 1MB in bytes

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setFileError(null);
    setPredictions([]);

    if (file) {
      if (file.size > MAX_FILE_SIZE) {
        setFileError('File size exceeds 1MB. Please use the API for larger files.');
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }

      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      setIsLoading(true);

      try {
        let parsed: ParsedData;
        if (fileExtension === 'csv') {
          parsed = await parseCSV(file);
        } else if (fileExtension === 'pdf') {
          const content = await getTextFromFile(file);
          parsed = {
            type: 'pdf',
            content: content.join('\n'),
            pdfParagraphs: content,
          };
        } else if (['xls', 'xlsx'].includes(fileExtension ?? '')) {
          const excelRows = await parseExcel(file);
          parsed = {
            type: 'csv',
            content: excelRows.map((row) => row.content).join('\n\n'),
            rows: excelRows,
          };
        } else {
          parsed = { type: 'other', content: await parseTXT(file) };
        }

        setInputText(parsed.content);
        setParsedData(parsed);
        handleRun(parsed.content);
      } catch (error) {
        console.error('Error processing file:', error);
        setFileError('Error processing file. Please try again.');
      } finally {
        setIsLoading(false);
      }
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRun = async (text: string = inputText) => {
    if (text === '') {
      return;
    }
    setIsLoading(true);
    try {
      const result = await predict(text);
      setPredictions(
        result.predicted_classes.map(([name, score]) => [name, Math.floor(score * 100)])
      );
    } catch (error) {
      console.error('Error during prediction:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const renderPredictions = () => (
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
  );

  return (
    <div
      className="bg-muted"
      style={{
        width: '100%',
        display: 'flex',
        justifyContent: 'center',
        height: '100vh',
      }}
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
          <Box display="flex" flexDirection="column" width="100%">
            <Box display="flex" justifyContent="center" alignItems="center" width="100%">
              <label htmlFor="file-upload" style={{ marginRight: '10px' }}>
                <Button size="sm" asChild>
                  <span>Upload File</span>
                </Button>
              </label>
              <input
                ref={fileInputRef}
                id="file-upload"
                type="file"
                accept=".txt,.pdf,.docx,.csv,.xls,.xlsx"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <Input
                autoFocus
                className="text-md"
                style={{ height: '3rem', flex: 1 }}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Enter your text..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleRun();
                  }
                }}
              />
              <Button
                size="sm"
                style={{ height: '3rem', marginLeft: '10px', padding: '0 20px' }}
                onClick={() => handleRun()}
              >
                Run
              </Button>
            </Box>

            {fileError && (
              <Alert severity="error" style={{ marginTop: '8px' }}>
                {fileError}
              </Alert>
            )}

            <Typography variant="caption" display="block" mt={1}>
              Supported file types: .txt, .pdf, .docx, .csv, .xls, .xlsx (Max size: 1MB)
            </Typography>
          </Box>

          {isLoading ? (
            <Box mt={4} display="flex" justifyContent="center">
              <CircularProgress />
            </Box>
          ) : (
            predictions.length > 0 && renderPredictions()
          )}
        </Container>
      </Tabs>
    </div>
  );
}
