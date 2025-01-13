'use client';

declare module 'react' {
  interface InputHTMLAttributes<T> extends HTMLAttributes<T> {
    webkitdirectory?: string;
    directory?: string;
  }
}

import { useState, useRef, useCallback } from 'react';
import { Container, Box, CircularProgress, Typography, Alert } from '@mui/material';
import { Tabs } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import * as _ from 'lodash';
import { useTextClassificationEndpoints } from '@/lib/backend';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { parseCSV, parseExcel, parseTXT } from '@/utils/fileParsingUtils';
import InferenceTimeDisplay from '@/components/ui/InferenceTimeDisplay';
import { Loader2, CheckCircle2 } from 'lucide-react';

interface ParsedData {
  type: 'csv' | 'pdf' | 'other';
  content: string;
  rows?: { label: string; content: string }[];
  pdfParagraphs?: string[];
}

interface FileResult {
  filename: string;
  predictions: [string, number][];
  processingTime?: number;
}

export default function Page() {
  const { workflowName, predict, getTextFromFile } = useTextClassificationEndpoints();
  const [inputText, setInputText] = useState('');
  const [predictions, setPredictions] = useState<[string, number][]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<ParsedData | null>(null);
  const [processingTime, setProcessingTime] = useState<number | null>(null);
  const [folderResults, setFolderResults] = useState<FileResult[]>([]);
  const [processingFolder, setProcessingFolder] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [skippedFiles, setSkippedFiles] = useState<string[]>([]);

  const MAX_FILE_SIZE = 1024 * 1024;

  const handleFolderUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []).filter((file) => {
      const extension = file.name.split('.').pop()?.toLowerCase();
      return ['txt', 'pdf', 'docx', 'csv', 'xls', 'xlsx', 'html'].includes(extension ?? '');
    });

    if (files.length === 0) {
      setFileError('No supported files found in the folder');
      return;
    }

    setProcessingFolder(true);
    setFolderResults([]);
    setPredictions([]);
    setProcessingTime(null);
    setInputText('');
    setSkippedFiles([]); // Reset skipped files

    try {
      const oversizedFiles: string[] = [];

      // Process files sequentially with delay
      for (const file of files) {
        if (file.size > MAX_FILE_SIZE) {
          oversizedFiles.push(file.name);
          continue;
        }

        const startTime = performance.now();
        const fileExtension = file.name.split('.').pop()?.toLowerCase();

        try {
          // Add a small delay between files
          await new Promise((resolve) => setTimeout(resolve, 500));

          let content: string;
          if (fileExtension === 'csv') {
            const parsed = await parseCSV(file);
            content = parsed.content;
          } else if (['pdf', 'docx', 'html'].includes(fileExtension ?? '')) {
            // Create a new FileReader for each file
            const fileBuffer = await new Promise<ArrayBuffer>((resolve) => {
              const reader = new FileReader();
              reader.onload = (e) => resolve(e.target?.result as ArrayBuffer);
              reader.readAsArrayBuffer(file);
            });

            // Create a new File object with the buffer
            const newFile = new File([fileBuffer], file.name, { type: file.type });
            const textContent = await getTextFromFile(newFile);
            content = textContent.join('\n');
          } else if (['xls', 'xlsx'].includes(fileExtension ?? '')) {
            const excelRows = await parseExcel(file);
            content = excelRows.map((row) => row.content).join('\n\n');
          } else {
            content = await parseTXT(file);
          }

          const predictions = await predict(content);
          const processingTime = performance.now() - startTime;

          setFolderResults((prev) => [
            ...prev,
            {
              filename: file.name,
              predictions: predictions.data.prediction_results.predicted_classes.map(
                ([name, score]) => [name, Math.floor(score * 100)]
              ),
              processingTime,
            },
          ]);
        } catch (error) {
          console.error(`Error processing file ${file.name}:`, error);
          // Continue processing other files even if one fails
        }
      }

      if (oversizedFiles.length > 0) {
        setSkippedFiles(oversizedFiles);
        setFileError(`${oversizedFiles.length} files exceeded 1MB size limit and were skipped.`);
      }
    } catch (error) {
      console.error('Error processing folder:', error);
      setFileError('Error processing folder files');
    } finally {
      setProcessingFolder(false);
      if (folderInputRef.current) {
        folderInputRef.current.value = '';
      }
    }
  };

  // Add this below the file error alert
  {
    skippedFiles.length > 0 && (
      <div className="mt-2 text-sm text-gray-500">Skipped files: {skippedFiles.join(', ')}</div>
    );
  }

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
        } else if (['pdf', 'docx', 'html'].includes(fileExtension ?? '')) {
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
    setFolderResults([]); // Clear folder results
    try {
      const result = await predict(text);
      console.log('result', result);
      setPredictions(
        result.data.prediction_results.predicted_classes.map(([name, score]) => [
          name,
          Math.floor(score * 100),
        ])
      );
      setProcessingTime(result.data.time_taken);
    } catch (error) {
      console.error('Error during prediction:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const renderPredictionRow = (prediction: [string, number], isHighest: boolean) => (
    <div
      className={`flex justify-between items-center p-4 rounded-lg transition-colors ${
        isHighest ? 'bg-green-50 border border-green-200' : 'hover:bg-gray-50'
      }`}
    >
      <div className="flex items-center gap-2">
        {isHighest && <CheckCircle2 className="text-green-500 w-5 h-5" />}
        <span className={`text-lg ${isHighest ? 'font-medium' : ''}`}>
          {prediction[0].replace(/_/g, ' ')}
        </span>
      </div>
      <div
        className={`px-4 py-2 rounded-full ${
          isHighest ? 'bg-green-100 text-green-700' : 'bg-gray-100'
        }`}
      >
        {prediction[1]}%
      </div>
    </div>
  );

  const renderPredictions = () => {
    const maxProbability = Math.max(...predictions.map((p) => p[1]));

    return (
      <Box mt={4} display="flex" gap={4}>
        <div style={{ flex: 2 }}>
          <Card className="bg-white p-4">
            <CardTitle className="mb-4">Classification Results</CardTitle>
            <div className="space-y-2">
              {predictions.map((prediction, index) => (
                <div key={index}>
                  {renderPredictionRow(prediction, prediction[1] === maxProbability)}
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div style={{ flex: 1 }}>
          {processingTime !== null && <InferenceTimeDisplay processingTime={processingTime} />}
        </div>
      </Box>
    );
  };

  const renderFolderResults = () => (
    <Box mt={4}>
      {folderResults.map((result, index) => {
        const maxProbability = Math.max(...result.predictions.map((p) => p[1]));

        return (
          <Card key={index} className="mb-4 bg-white">
            <CardHeader>
              <CardTitle className="text-lg font-semibold">{result.filename}</CardTitle>
            </CardHeader>
            <div className="p-4 space-y-2">
              {result.predictions.map((prediction, pIndex) => (
                <div key={pIndex}>
                  {renderPredictionRow(prediction, prediction[1] === maxProbability)}
                </div>
              ))}
              {result.processingTime && (
                <div className="text-sm text-muted-foreground mt-4 text-right">
                  Processed in {(result.processingTime / 1000).toFixed(2)}s
                </div>
              )}
            </div>
          </Card>
        );
      })}
    </Box>
  );

  return (
    <div
      className="bg-muted"
      style={{ width: '100%', display: 'flex', justifyContent: 'center', height: '100vh' }}
    >
      <Tabs defaultValue="interact" style={{ width: '100%' }}>
        <div style={{ position: 'fixed', top: '20px', left: '20px' }}>
          <div className="text-muted-foreground" style={{ fontSize: '16px' }}>
            Doc Classification
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
            <Box display="flex" justifyContent="center" alignItems="center" width="100%" gap={2}>
              <label htmlFor="file-upload">
                <Button size="sm" asChild>
                  <span>Upload File</span>
                </Button>
              </label>
              <label htmlFor="folder-upload">
                <Button size="sm" variant="outline" asChild>
                  <span>Upload Folder</span>
                </Button>
              </label>
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
                style={{ height: '3rem', padding: '0 20px' }}
                onClick={() => handleRun()}
              >
                Run
              </Button>
            </Box>

            <input
              ref={fileInputRef}
              id="file-upload"
              type="file"
              accept=".txt,.pdf,.docx,.csv,.xls,.xlsx"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <input
              ref={folderInputRef}
              id="folder-upload"
              type="file"
              webkitdirectory=""
              directory=""
              multiple
              onChange={handleFolderUpload}
              style={{ display: 'none' }}
            />

            {fileError && (
              <Alert severity="error" style={{ marginTop: '8px' }}>
                {fileError}
              </Alert>
            )}

            <Typography variant="caption" display="block" mt={1}>
              Supported files: .txt, .pdf, .docx, .csv, .xls, .xlsx (Max: 1MB) or folder containing
              any of these file types
            </Typography>
          </Box>

          {processingFolder ? (
            <Box mt={4} display="flex" justifyContent="center" alignItems="center" gap={2}>
              <Loader2 className="animate-spin" />
              <span>Processing folder... ({folderResults.length} files done)</span>
            </Box>
          ) : isLoading ? (
            <Box mt={4} display="flex" justifyContent="center">
              <CircularProgress />
            </Box>
          ) : (
            <>
              {predictions.length > 0 && renderPredictions()}
              {folderResults.length > 0 && renderFolderResults()}
            </>
          )}
        </Container>
      </Tabs>
    </div>
  );
}
