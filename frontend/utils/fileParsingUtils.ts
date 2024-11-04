// fileParsingUtils.ts

import * as XLSX from 'xlsx';
import Papa from 'papaparse';

export interface ParsedData {
  type: 'csv' | 'pdf' | 'other';
  content: string;
  rows?: { label: string; content: string }[];
  pdfParagraphs?: string[];
}

export const parseCSV = (file: File): Promise<ParsedData> => {
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
          .filter((row) => row.some((cell) => cell.trim() !== ''))
          .map((row, rowIndex) => {
            let content = headers
              .map((header, index) => `${header}: ${row[index] || ''}`)
              .join('\n');
            return {
              label: `Row ${rowIndex + 1}`,
              content: content,
            };
          });
        const fullContent = parsedRows.map((row) => row.content).join('\n\n');
        resolve({ type: 'csv', content: fullContent, rows: parsedRows });
      },
      error: reject,
    });
  });
};

export const parseExcel = (file: File): Promise<{ label: string; content: string }[]> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const data = new Uint8Array(e.target?.result as ArrayBuffer);
      const workbook = XLSX.read(data, { type: 'array' });
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 }) as (
        | string
        | number
        | null
      )[][];

      if (jsonData.length < 2) {
        resolve([]);
        return;
      }

      const headers = jsonData[0].map(String);
      const rows = jsonData.slice(1);

      let parsedRows = rows
        .map((row, rowIndex) => {
          if (row.some((cell) => cell !== null && cell !== '')) {
            let content = headers
              .map((header, index) => {
                const cellValue = row[index];
                return `${header}: ${cellValue !== null && cellValue !== undefined ? cellValue : ''}`;
              })
              .join('\n');
            return {
              label: `Row ${rowIndex + 1}`,
              content: content,
            };
          }
          return null;
        })
        .filter((row): row is { label: string; content: string } => row !== null);

      resolve(parsedRows);
    };
    reader.onerror = reject;
    reader.readAsArrayBuffer(file);
  });
};

export const parseTXT = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      resolve(e.target?.result as string);
    };
    reader.onerror = reject;
    reader.readAsText(file);
  });
};

export const convertCSVToPDFFormat = (
  rows: { label: string; content: string }[]
): { words: { text: string; originalIndex: number }[]; rowIndices: number[] } => {
  let globalIndex = 0;
  const words: { text: string; originalIndex: number }[] = [];
  const rowIndices: number[] = [];

  rows.forEach((row, index) => {
    rowIndices.push(globalIndex);
    const trimmedContent = row.content.replace(/\s+/g, ' ').trim();
    const rowWords = trimmedContent.split(' ').filter((word) => word !== '');
    rowWords.forEach((word) => {
      words.push({ text: word, originalIndex: globalIndex });
      globalIndex++;
    });
  });
  rowIndices.push(globalIndex);

  return { words, rowIndices };
};
