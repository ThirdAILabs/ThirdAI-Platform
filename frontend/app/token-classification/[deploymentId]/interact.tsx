'use client';
import React from 'react';
import { Container, Box, CircularProgress, Typography, Switch, FormControlLabel } from '@mui/material';
import { Button } from '@/components/ui/button';
import { MouseEventHandler, ReactNode, useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/card';
import * as _ from 'lodash';
import { useTokenClassificationEndpoints } from '@/lib/backend';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import Fuse from 'fuse.js';
import mammoth from 'mammoth'; // DOCX Parsing
import * as XLSX from 'xlsx';
import Papa from 'papaparse';
// @ts-ignore
import * as pdfjsLib from 'pdfjs-dist/build/pdf'; // Importing PDF.js as you do in your PdfViewer
// @ts-ignore
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.entry'; // Importing worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

interface Token {
  text: string;
  tag: string;
}

interface HighlightColor {
  text: string;
  tag: string;
}

interface HighlightProps {
  currentToken: Token;
  nextToken?: Token | null;
  tagColors: Record<string, HighlightColor>;
  onMouseOver: MouseEventHandler;
  onMouseDown: MouseEventHandler;
  selecting: boolean;
  selected: boolean;
}

interface ParsedData {
  type: 'csv' | 'pdf' | 'other';
  content: string;
  rows?: { label: string; content: string }[];
}


const SELECTING_COLOR = '#EFEFEF';
const SELECTED_COLOR = '#DFDFDF';

function Highlight({
  currentToken,
  nextToken,
  tagColors,
  onMouseOver,
  onMouseDown,
  selecting,
  selected,
}: HighlightProps) {
  const [hover, setHover] = useState<boolean>(false);

  return (
    <>
      <span
        style={{
          backgroundColor:
            hover || selecting
              ? SELECTING_COLOR
              : selected
                ? SELECTED_COLOR
                : tagColors[currentToken.tag]?.text || 'transparent',
          padding: '2px',
          borderRadius: '2px',
          cursor: hover ? 'pointer' : 'default',
          userSelect: 'none',
        }}
        onMouseOver={(e) => {
          setHover(true);
          onMouseOver(e);
        }}
        onMouseLeave={(e) => {
          setHover(false);
        }}
        onMouseDown={onMouseDown}
      >
        {currentToken.text}
        {tagColors[currentToken.tag] && nextToken?.tag !== currentToken.tag && (
          <span
            style={{
              backgroundColor: tagColors[currentToken.tag].tag,
              color: 'white',
              fontSize: '11px',
              fontWeight: 'bold',
              borderRadius: '2px',
              marginLeft: '4px',
              padding: '5px 3px 1px 3px',
              marginBottom: '1px',
            }}
          >
            {currentToken.tag}
          </span>
        )}
      </span>
      <span
        style={{ cursor: hover ? 'pointer' : 'default', userSelect: 'none' }}
        onMouseOver={(e) => {
          setHover(true);
          onMouseOver(e);
        }}
        onMouseLeave={(e) => {
          setHover(false);
        }}
        onMouseDown={onMouseDown}
      >
        {' '}
      </span>
    </>
  );
}

interface TagSelectorProps {
  open: boolean;
  choices: string[];
  onSelect: (tag: string) => void;
}

function TagSelector({ open, choices, onSelect }: TagSelectorProps) {
  const [fuse, setFuse] = useState(new Fuse(choices));
  const [query, setQuery] = useState('');
  useEffect(() => {
    setFuse(new Fuse(choices));
  }, [choices]);
  const searchResults = query !== '' ? fuse.search(query).map((val) => val.item) : choices;
  const makeDropdownMenuItem = (key: number, value: string, child: ReactNode) => (
    <DropdownMenuItem className="font-medium" key={key}>
      <button
        style={{ width: '100%', height: '100%', textAlign: 'left' }}
        onClick={() => {
          onSelect(value);
          setQuery('');
        }}
      >
        {child}
      </button>
    </DropdownMenuItem>
  );
  return (
    <DropdownMenu open={open} modal={false}>
      <DropdownMenuTrigger>
        <span />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <Input
          autoFocus
          className="font-medium"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ marginBottom: '5px' }}
          onKeyDown={(e) => {
            e.stopPropagation();
          }}
        />
        {searchResults.map((val, index) => makeDropdownMenuItem(index, val, val))}
        {query !== '' &&
          !searchResults.map((val) => val).includes(query) &&
          makeDropdownMenuItem(
            /* key= */ 0,
            query,
            <>
              <span
                className="bg-accent font-medium"
                style={{
                  padding: '0 3px',
                  marginRight: '5px',
                  borderRadius: '2px',
                  fontWeight: 'bold',
                }}
                onClick={() => onSelect(query)}
              >
                New{' '}
              </span>{' '}
              {query}
            </>
          )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function Interact() {
  const { predict } = useTokenClassificationEndpoints();

  const [inputText, setInputText] = useState<string>('');
  const [annotations, setAnnotations] = useState<Token[]>([]);
  const [tagColors, setTagColors] = useState<Record<string, HighlightColor>>({});
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const [mouseDownIndex, setMouseDownIndex] = useState<number | null>(null);
  const [mouseUpIndex, setMouseUpIndex] = useState<number | null>(null);
  const [selecting, setSelecting] = useState<boolean>(false);
  const startIndex =
    mouseDownIndex !== null && mouseUpIndex !== null
      ? Math.min(mouseDownIndex, mouseUpIndex)
      : null;
  const endIndex =
    mouseDownIndex !== null && mouseUpIndex !== null
      ? Math.max(mouseDownIndex, mouseUpIndex)
      : null;
  const [selectedRange, setSelectedRange] = useState<[number, number] | null>(null);

  const triggers = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    const stopSelectingOnOutsideClick = () => {
      setSelecting(false);
      setSelectedRange(null);
    };
    window.addEventListener('mousedown', stopSelectingOnOutsideClick);
    return stopSelectingOnOutsideClick;
  }, []);

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(event.target.value);
    // Reset parsedData when manually typing
    setParsedData(null);
    setAnnotations([]);
  };

  // Add a new state to store the parsed rows
  const [parsedRows, setParsedRows] = useState<{label: string, content: string}[]>([]);

  const parseCSV = (file: File): Promise<ParsedData> => {
    return new Promise((resolve, reject) => {
      Papa.parse(file, {
        complete: (results) => {
          const data = results.data as string[][];
          if (data.length < 2) {
            resolve({ type: 'csv', content: '', rows: [] });
            return;
          }
          const headers = data[0];
          const rows = data.slice(1);
          let parsedRows = rows
            .filter(row => row.some(cell => cell.trim() !== ''))
            .map((row, rowIndex) => {
              let content = headers.map((header, index) => `${header}: ${row[index] || ''}`).join('\n');
              return {
                label: `Row ${rowIndex + 1}`,
                content: content
              };
            });
          const fullContent = parsedRows.map(row => row.content).join('\n\n');
          resolve({ type: 'csv', content: fullContent, rows: parsedRows });
        },
        error: reject,
      });
    });
  };

  const parseExcel = (file: File): Promise<{label: string, content: string}[]> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const workbook = XLSX.read(data, { type: 'array' });
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 }) as (string | number | null)[][];
        
        if (jsonData.length < 2) {
          resolve([]);
          return;
        }
        
        const headers = jsonData[0].map(String);
        const rows = jsonData.slice(1);
        
        let parsedRows = rows.map((row, rowIndex) => {
          if (row.some(cell => cell !== null && cell !== '')) {
            let content = headers.map((header, index) => {
              const cellValue = row[index];
              return `${header}: ${cellValue !== null && cellValue !== undefined ? cellValue : ''}`;
            }).join('\n');
            return {
              label: `Row ${rowIndex + 1}`,
              content: content
            };
          }
          return null;
        }).filter((row): row is {label: string, content: string} => row !== null);
        
        resolve(parsedRows);
      };
      reader.onerror = reject;
      reader.readAsArrayBuffer(file);
    });
  };

  const [parsedData, setParsedData] = useState<ParsedData | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Update the handleFileChange function
  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      setIsLoading(true);

      let parsed: ParsedData;
      if (fileExtension === 'csv') {
        parsed = await parseCSV(file);
      } else if (fileExtension === 'pdf') {
        parsed = await parsePDF(file);
      } else if (['xls', 'xlsx'].includes(fileExtension ?? '')) {
        const excelRows = await parseExcel(file);
        parsed = { type: 'csv', content: excelRows.map(row => row.content).join('\n\n'), rows: excelRows };
      } else {
        // Handle other file types (txt, docx)
        const content = fileExtension === 'docx' ? await parseDOCX(file) : await parseTXT(file);
        parsed = { type: 'other', content };
      }

      setInputText(parsed.content);
      setParsedData(parsed);
      handleRun(parsed.content, true); // Pass true to indicate it's a file upload
      setIsLoading(false);
    }

    // Reset the file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const parseTXT = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        resolve(e.target?.result as string);
      };
      reader.onerror = reject;
      reader.readAsText(file);
    });
  };

  interface PDFTextItem {
    text: string;
    x: number;
    y: number;
    fontName: string;
    height: number;
  }
  
  const parsePDF = async (file: File): Promise<ParsedData> => {
    const loadingTask = pdfjsLib.getDocument(URL.createObjectURL(file));
    const pdf = await loadingTask.promise;
    let fullText = '';

    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
      const page = await pdf.getPage(pageNum);
      const textContent = await page.getTextContent();
      let lastY = Infinity;
      let lastHeight = 0;
      let currentParagraph = '';
      let paragraphs: string[] = [];

      const pageItems = textContent.items
        .map((item: any) => ({ 
          text: item.str, 
          x: item.transform[4],
          y: item.transform[5],
          fontName: item.fontName,
          height: item.height
        }))
        .sort((a: PDFTextItem, b: PDFTextItem) => b.y - a.y || a.x - b.x);  // Sort by y (descending) then x (ascending)
  
      pageItems.forEach((curr: PDFTextItem, index: number) => {
        const verticalGap = lastY - (curr.y + curr.height);
        
        if (index > 0) {
          // Check if this item is on a new paragraph
          if (verticalGap > Math.max(lastHeight, curr.height) * 1.5) {  // Significant gap, likely a new paragraph
            if (currentParagraph.trim() !== '') {
              paragraphs.push(currentParagraph.trim());
              currentParagraph = '';
            }
            if (paragraphs.length > 0) {
              paragraphs.push('');  // Add an empty line between paragraphs
            }
          }
          // Add space if needed within the same paragraph
          if (curr.x - (pageItems[index - 1].x + pageItems[index - 1].text.length * 5) > 10) {
            currentParagraph += ' ';
          }
        }
        
        currentParagraph += curr.text;
        lastY = curr.y;
        lastHeight = curr.height;
      });
  
      // Add the last paragraph if it's not empty
      if (currentParagraph.trim() !== '') {
        paragraphs.push(currentParagraph.trim());
      }

      fullText += paragraphs.join('\n') + '\n';  // Join paragraphs and add newline between pages
    }

    fullText = fullText.replace(/^PDF:\s*/i, '').trim();
    return { type: 'pdf', content: fullText };
  };

  const parseDOCX = async (file: File) => {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value;
  };

  const updateTagColors = (tags: string[][]) => {
    const pastels = ['#E5A49C', '#F6C886', '#FBE7AA', '#99E3B5', '#A6E6E7', '#A5A1E1', '#D8A4E2'];
    const darkers = ['#D34F3E', '#F09336', '#F7CF5F', '#5CC96E', '#65CFD0', '#597CE2', '#B64DC8'];

    setTagColors((existingColors) => {
      const colors = { ...existingColors };
      const newTags = Array.from(new Set(tags.flatMap((tokenTags) => tokenTags))).filter(
        (tag) => !existingColors[tag] && tag !== 'O'
      );
      newTags.forEach((tag, index) => {
        const i = Object.keys(existingColors).length + index;
        colors[tag] = {
          text: pastels[i % pastels.length],
          tag: darkers[i % darkers.length],
        };
      });
      return colors;
    });
  };

  const handleRun = (text: string, isFileUpload: boolean = false) => {
    setIsLoading(true);
    predict(text).then((result) => {
      updateTagColors(result.predicted_tags);
      setAnnotations(
        _.zip(result.tokens, result.predicted_tags).map(([text, tag]) => ({
          text: text as string,
          tag: tag![0] as string,
        }))
      );
  
      // Only set parsedData for direct text input, not file uploads
      if (!isFileUpload && !parsedData) {
        setParsedData({ type: 'other', content: text });
      }
      
      setIsLoading(false);
    });
  };

  const renderContent = () => {
    if (!parsedData) return null;

    if (parsedData.type === 'csv' && parsedData.rows) {
      return renderCSVContent(parsedData.rows);
    } else if (parsedData.type === 'pdf') {
      return renderPDFContent(parsedData.content);
    } else {
      return renderHighlightedContent(parsedData.content);
    }
  };

  const finetuneTags = (newTag: string) => {
    setAnnotations((prev) =>
      prev.map(({ text, tag }, idx) =>
        selectedRange && idx >= selectedRange[0] && idx <= selectedRange[1]
          ? { text, tag: newTag }
          : { text, tag }
      )
    );
    updateTagColors([[newTag]]);
    setSelectedRange(null);
    setMouseDownIndex(null);
    setMouseUpIndex(null);
    setSelecting(false);
  };

  const [showHighlightedOnly, setShowHighlightedOnly] = useState(false);

  const toggleHighlightedOnly = (event: React.ChangeEvent<HTMLInputElement>) => {
    setShowHighlightedOnly(event.target.checked);
  };

  const isWordHighlighted = (word: string) => {
    return annotations.some(token => 
      token.text.toLowerCase() === word.toLowerCase() &&
      token.tag !== 'O'
    );
  };

  const renderCSVContent = (rows: { label: string; content: string }[]) => {
    return rows.map((row, rowIndex) => {
      const columns = row.content.split('\n');
      const visibleColumns = columns.filter(column => {
        const [columnName, ...columnContent] = column.split(':');
        const content = columnContent.join(':').trim();
        return !showHighlightedOnly || content.split(' ').some(isWordHighlighted);
      });
  
      if (visibleColumns.length === 0) {
        return null;
      }
  
      return (
        <div key={rowIndex} style={{ marginBottom: '20px', padding: '10px', border: '1px solid #ccc', borderRadius: '5px' }}>
          <strong>{row.label}:</strong>
          {visibleColumns.map((column, columnIndex) => {
            const [columnName, ...columnContent] = column.split(':');
            const content = columnContent.join(':').trim();
            return (
              <p key={columnIndex}>
                <strong>{columnName}:</strong>{' '}
                {renderHighlightedContent(content)}
              </p>
            );
          })}
        </div>
      );
    });
  };

  // Update the renderPDFContent function to handle the new format
  const renderPDFContent = (content: string) => {
    return content.split('\n').map((paragraph, index) => (
      <React.Fragment key={index}>
        {paragraph === '' ? <br /> : renderHighlightedContent(paragraph)}
        <br />
      </React.Fragment>
    ));
  };

  const renderHighlightedContent = (content: string) => {
    const words = content.split(/\s+/);
    return words.map((word, wordIndex) => {
      const tokenIndex = annotations.findIndex(token => 
        token.text.toLowerCase() === word.toLowerCase()
      );
  
      if (tokenIndex !== -1 && annotations[tokenIndex].tag !== 'O') {
        return (
          <Highlight
            key={wordIndex}
            currentToken={annotations[tokenIndex]}
            nextToken={annotations[tokenIndex + 1] || null}
            tagColors={tagColors}
            onMouseOver={(e) => {
              if (selecting) {
                setMouseUpIndex(tokenIndex);
              }
            }}
            onMouseDown={(e) => {
              e.stopPropagation();
              setSelecting(true);
              setMouseDownIndex(tokenIndex);
              setMouseUpIndex(tokenIndex);
              setSelectedRange(null);
            }}
            selecting={
              selecting &&
              startIndex !== null &&
              endIndex !== null &&
              tokenIndex >= startIndex &&
              tokenIndex <= endIndex
            }
            selected={
              selectedRange !== null &&
              tokenIndex >= selectedRange[0] &&
              tokenIndex <= selectedRange[1]
            }
          />
        );
      }
      return showHighlightedOnly ? null : <span key={wordIndex}>{word} </span>;
    });
  };

  return (
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
          onChange={handleInputChange}
          placeholder="Enter your text..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleRun(inputText);
            }
          }}
        />
        <Button 
          size="sm" 
          onClick={() => handleRun(inputText)} 
          style={{ marginLeft: '10px' }}
        >
          Run
        </Button>
      </Box>

      <Typography variant="caption" display="block" mt={1}>
        Supported file types: .txt, .pdf, .docx, .csv, .xls, .xlsx
      </Typography>

      {annotations.length > 0 && (
        <Box mt={4} mb={2} display="flex" alignItems="center" justifyContent="flex-end">
          <FormControlLabel
            control={
              <Switch
                checked={showHighlightedOnly}
                onChange={toggleHighlightedOnly}
                color="primary"
              />
            }
            label="Tagged Text Only"
          />
        </Box>
      )}

      {isLoading ? (
        <Box mt={4} display="flex" justifyContent="center">
          <CircularProgress />
        </Box>
      ) : (
        annotations.length > 0 && (
          <Box mt={4}>
            <Card
              className="p-7 text-start"
              style={{ 
                lineHeight: 1.6,  // Adjusted for better readability
                fontWeight: 'normal',
                whiteSpace: 'pre-wrap',  // This will preserve whitespace and line breaks
                wordWrap: 'break-word'   // This will wrap long words
              }}
              onMouseUp={(e) => {
                setSelecting(false);
                if (startIndex !== null && endIndex !== null) {
                  setSelectedRange([startIndex, endIndex]);
                  triggers.current[endIndex]?.click();
                }
              }}
            >
              {renderContent()}
              {annotations.map((_, index) => (
                <TagSelector
                  key={index}
                  open={!!selectedRange && index === selectedRange[1]}
                  choices={Object.keys(tagColors)}
                  onSelect={finetuneTags}
                />
              ))}
            </Card>
          </Box>
        )
      )}
    </Container>
  );
}
