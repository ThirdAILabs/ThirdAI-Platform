import { Box, Chunk, DocChunks } from './components/pdf_viewer/interfaces';
import { temporaryCacheToken } from '@/lib/backend';
import _ from 'lodash';

export const deploymentBaseUrl = typeof window !== 'undefined' ? window.location.origin : '';

export interface ReferenceJson {
  id: number;
  source: string;
  text: string;
  metadata: any;
}

export interface ReferenceInfo {
  id: number;
  sourceURL: string;
  sourceName: string;
  content: string;
  metadata: any;
}

export interface PiiEntity {
  token: string;
  label: string;
}

export interface SearchResult {
  queryId: string;
  query: string;
  references: ReferenceInfo[];

  pii_entities: PiiEntity[] | null;
}

export interface PdfInfo {
  filename: string;
  source: string;
  docChunks: DocChunks;
  highlighted: Chunk;
}

export interface ChatMessage {
  sender: string;
  content: string;
}

export interface ChatResponse {
  response: string;
}

export interface Source {
  source: string;
  source_id: string;
}

export interface PIIDetectionResult {
  tokens: string[];
  predicted_tags: string[];
}

function sourceName(ref: ReferenceJson) {
  if (ref.source.endsWith('.pdf') || ref.source.endsWith('.docx')) {
    return ref.source.split('/').at(-1);
  }
  if ('title' in ref.metadata) {
    return ref.metadata['title'];
  }
  return ref.source;
}

function startAndEnd(text: string, n_words: number = 2) {
  const trimmed = text.replace(/^[^a-z\d]*|[^a-z\d]*$/gi, '');

  let startSpaces = 0;
  let startEnd = 0;
  for (; startEnd < trimmed.length; startEnd++) {
    if (trimmed[startEnd] === ' ') {
      startSpaces++;
    }
    if (startSpaces === n_words) {
      break;
    }
  }

  let endSpaces = 0;
  let endStart = trimmed.length - 1;
  for (; endStart >= 0; endStart--) {
    if (trimmed[endStart] === ' ') {
      endSpaces++;
    }
    if (endSpaces === n_words) {
      break;
    }
  }

  return [trimmed.substring(0, startEnd), trimmed.substring(endStart + 1)];
}

type ImplicitFeecback = {
  reference_id: number;
  reference_rank: number;
  query_text: string;
  event_desc: string;
};

export class ModelService {
  url: string;
  ragUrl: string | undefined;
  sessionId: string;
  authToken: string | null;

  constructor(url: string, ragUrl: string | undefined, sessionId: string) {
    this.url = url;
    this.ragUrl = ragUrl;
    this.sessionId = sessionId;
    this.authToken = window.localStorage.getItem('accessToken');
  }

  authHeader(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.authToken}`,
      'Cache-Control': 'no-cache',
    };
  }

  handleInvalidAuth() {
    return (response: Response) => {
      if (response.status == 401) {
        alert(
          'You do not have the correct permissions. Please sign into Model Bazaar with the correct credentials.'
        );
      }
      return response;
    };
  }

  getModelID(): string {
    function extractModelIdFromUrl(url: string) {
      const urlParts = new URL(url);
      const pathSegments = urlParts.pathname.split('/');
      return pathSegments[pathSegments.length - 1]; // Assumes the modelId is the last segment
    }

    const modelId = extractModelIdFromUrl(this.url);

    return modelId;
  }

  async sources(): Promise<Source[]> {
    const url = new URL(this.url + '/sources');
    return fetch(url, { headers: this.authHeader() })
      .then(this.handleInvalidAuth())
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
      })
      .then(({ data }) => {
        return data;
      })
      .catch((e) => {
        return [];
      });
  }

  async saveModel(override: boolean, model_name?: string): Promise<any> {
    const url = new URL(this.url + '/save');
    const payload = {
      override,
      model_name: model_name || null,
    };

    return fetch(url, {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: {
        ...this.authHeader(),
        'Content-Type': 'application/json',
      },
    })
      .then(this.handleInvalidAuth())
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
        return response.json().then((json) => {
          throw new Error(json.message);
        });
      })
      .then((data) => {
        console.log('Model saved successfully:', data);
        return data;
      })
      .catch((e) => {
        console.error('Error saving model:', e);
        alert('Error saving model:' + e);
        throw e;
      });
  }

  async addSources(files: File[], s3Urls: string[]): Promise<any> {
    const formData = new FormData();
    const documents: object[] = [];

    // Process local files
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
      const extension = files[i].name.split('.').pop();
      documents.push({
        document_type: extension!.toUpperCase(),
        path: files[i].name,
        location: 'local',
        metadata: {},
        chunk_size: 100,
        stride: 40,
        emphasize_first_words: 0,
        ignore_header_footer: true,
        ignore_nonstandard_orientation: true,
      });
    }

    // Process S3 URLs
    for (let i = 0; i < s3Urls.length; i++) {
      const url = s3Urls[i];
      const extension = url.split('.').pop();
      documents.push({
        document_type: extension ? extension.toUpperCase() : 'URL',
        path: url,
        location: 's3',
        metadata: {},
        chunk_size: 100,
        stride: 40,
        emphasize_first_words: 0,
        ignore_header_footer: true,
        ignore_nonstandard_orientation: true,
      });
    }

    // Wrap the documents array in an object with a 'documents' key
    formData.append('documents', JSON.stringify({ documents }));
    const url = new URL(this.url + '/insert');

    return fetch(url, {
      method: 'POST',
      body: formData,
      headers: {
        ...this.authHeader(),
      },
    })
      .then(this.handleInvalidAuth())
      .then(async (response) => {
        if (response.ok) {
          return response.json();
        }
        const errorBody = await response.json();
        throw new Error(JSON.stringify(errorBody));
      })
      .then(({ data }) => {
        return data;
      })
      .catch((e) => {
        console.error('Error in addSources:', e);
        throw e;
      });
  }

  async deleteSources(sourceIDs: string[]): Promise<any> {
    console.log(this.url);
    const url = new URL(this.url + '/delete');
    return fetch(url, {
      method: 'POST',
      body: JSON.stringify({
        source_ids: sourceIDs,
      }),
      headers: {
        ...this.authHeader(),
        'Content-Type': 'application/json',
      },
    })
      .then(this.handleInvalidAuth())
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
      })
      .then(({ data }) => {
        return data;
      })
      .catch((e) => {
        console.log(e);
        return [];
      });
  }

  async predict(queryText: string, topK: number, queryId?: string): Promise<SearchResult | null> {
    const requestUrl = this.ragUrl || this.url;
    const url = new URL(requestUrl + '/search');

    console.log('REQUST URL: ', url);

    return fetch(url, {
      method: 'POST',
      headers: {
        ...this.authHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: queryText, top_k: topK, constraints: {} }),
    })
      .then(this.handleInvalidAuth())
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
        throw new Error('Network response was not ok');
      })
      .then(({ data }) => {
        const searchResults: SearchResult = {
          queryId: queryId ?? data['query_id'],
          query: data['query_text'],
          references: data['references'].map((ref: any) => ({
            id: ref.id,
            sourceURL: ref.source,
            sourceName: sourceName(ref),
            content: ref.text,
            metadata: ref.metadata,
          })),
          pii_entities: data.pii_entities,
        };
        return searchResults;
      })
      .catch((e) => {
        console.error('Error in predict method:', e);
        return null;
      });
  }

  async unredact(text: string, pii_map: Map<string, Map<string, string>>): Promise<string> {
    const url = new URL(this.ragUrl + '/unredact');
    return fetch(url, {
      method: 'POST',
      headers: {
        ...this.authHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text: text, pii_map: pii_map }),
    })
      .then(this.handleInvalidAuth())
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
      })
      .then(({ data }) => {
        return data['unredacted_text'];
      })
      .catch((e) => {
        console.log(e);
        return '';
      });
  }

  getPdfInfo(reference: ReferenceInfo): Promise<PdfInfo> {
    const blobUrl = new URL(this.url + '/pdf-blob');
    blobUrl.searchParams.append('source', reference.sourceURL.toString());
    const blobPromise = fetch(blobUrl, { headers: this.authHeader() })
      .then(this.handleInvalidAuth())
      .then((res) => res.arrayBuffer())
      .then((data) => {
        var file = new Blob([data], { type: 'application/pdf' });
        return URL.createObjectURL(file);
      });

    const chunkUrl = new URL(this.url + '/pdf-chunks');
    chunkUrl.searchParams.append('reference_id', reference.id.toString());
    let highlighted: Chunk | null = null;
    const chunkPromise = fetch(chunkUrl, { headers: this.authHeader() })
      .then(this.handleInvalidAuth())
      .then((res) => res.json())
      .then(({ data }) => {
        const filename = data.filename as string;
        const ids = data.id as number[];
        const texts = data.text as string[];
        const boxes = data.boxes as [number, [number, number, number, number]][][];

        const docChunks: DocChunks = [];

        let row = 0;
        for (const rawChunkBoxes of boxes) {
          const matchingPageIdxs = new Set<number>();
          const chunkBoxes: Box[] = [];
          for (const [pageIdx, box] of rawChunkBoxes) {
            while (pageIdx >= docChunks.length) {
              docChunks.push([]);
            }
            matchingPageIdxs.add(pageIdx);
            const [left, top, right, bottom] = box;
            chunkBoxes.push({
              page: pageIdx,
              borders: { left, top, right, bottom },
            });
          }
          const chunk = {
            id: ids[row],
            text: texts[row],
            boxes: chunkBoxes,
          };
          for (const pageIdx of Array.from(matchingPageIdxs)) {
            docChunks[pageIdx].push(chunk);
          }
          if (ids[row] === reference.id) {
            highlighted = chunk;
          }
          row++;
        }
        return [filename, docChunks, highlighted] as [string, DocChunks, Chunk];
      });

    return Promise.all([blobPromise, chunkPromise]).then(
      ([source, [filename, docChunks, highlighted]]) => ({
        filename,
        source,
        docChunks,
        highlighted,
      })
    );
  }

  openHighlightedPDF(reference: ReferenceInfo) {
    const url = new URL(this.url + '/highlighted-pdf');
    url.searchParams.append('reference_id', reference.id.toString());
    fetch(url, { headers: this.authHeader() })
      .then(this.handleInvalidAuth())
      .then((res) => res.arrayBuffer())
      .then((data) => {
        var file = new Blob([data], { type: 'application/pdf' });
        var fileURL = URL.createObjectURL(file);
        window.open(fileURL + `#page=${reference.metadata['page'] + 1}`);
      })
      .catch(console.log);
  }

  openPDF(source: string) {
    const url = new URL(this.url + '/pdf-blob');
    url.searchParams.append('source', source.toString());
    fetch(url, { headers: this.authHeader() })
      .then(this.handleInvalidAuth())
      .then((res) => res.arrayBuffer())
      .then((data) => {
        var file = new Blob([data], { type: 'application/pdf' });
        var fileURL = URL.createObjectURL(file);
        window.open(fileURL);
      })
      .catch(console.log);
  }

  openHighlightedURL(reference: ReferenceInfo) {
    const [start, end] = startAndEnd(reference.content);
    const highlightedSourceURL = reference.sourceURL + '#:~:text=' + start + ',' + end;
    window.open(highlightedSourceURL);
  }

  openDOCX(source: string) {
    const viewingBaseUrl = 'http://docs.google.com/gview?url=';
    const path = source.substring(source.search('/documents'));
    window.open(viewingBaseUrl + this.url + path);
  }

  openReferenceSource(reference: ReferenceInfo): void {
    if (reference.sourceURL.toLowerCase().endsWith('.pdf')) {
      this.openHighlightedPDF(reference);
    } else if (reference.sourceURL.toLowerCase().endsWith('.docx')) {
      this.openDOCX(reference.sourceURL);
    } else {
      this.openHighlightedURL(reference);
    }
  }

  openSource(source: string): void {
    if (source.toLowerCase().endsWith('.pdf')) {
      this.openPDF(source);
    } else if (source.toLowerCase().endsWith('.docx')) {
      this.openDOCX(source);
    } else {
      window.open(source);
    }
  }

  openAWSReference(ref: ReferenceInfo): void {
    const [start, end] = startAndEnd(ref.content);
    const highlightedSourceURL =
      'https://' + ref.sourceURL.replace(/^(https?:\/\/)?/, '') + '#:~:text=' + start + ',' + end;
    window.open(highlightedSourceURL);
  }

  async upvote(
    queryId: string,
    queryText: string,
    referenceId: number,
    referenceText: string
  ): Promise<any> {
    return fetch(this.url + '/upvote', {
      method: 'POST',
      body: JSON.stringify({
        text_id_pairs: [
          {
            query_text: queryText,
            reference_id: referenceId,
            reference_text: referenceText
          },
        ],
      }),
      headers: {
        'Content-type': 'application/json; charset=UTF-8',
        ...this.authHeader(),
      },
    }).then(this.handleInvalidAuth());
  }

  async downvote(
    queryId: string,
    queryText: string,
    referenceId: number,
    referenceText: string
  ): Promise<any> {
    return fetch(this.url + '/downvote', {
      method: 'POST',
      body: JSON.stringify({
        text_id_pairs: [
          {
            query_text: queryText,
            reference_id: referenceId,
          },
        ],
      }),
      headers: {
        'Content-type': 'application/json; charset=UTF-8',
        ...this.authHeader(),
      },
    }).then(this.handleInvalidAuth());
  }

  async qna(question: string, answer: string): Promise<any> {
    return fetch(this.url + '/qna', {
      method: 'POST',
      body: JSON.stringify({
        qna_pairs: [
          {
            question: question,
            answer: answer,
          },
        ],
      }),
      headers: {
        'Content-type': 'application/json; charset=UTF-8',
        ...this.authHeader(),
      },
    }).then(this.handleInvalidAuth());
  }

  async associate(source: string, target: string): Promise<any> {
    return fetch(this.url + '/associate', {
      method: 'POST',
      body: JSON.stringify({
        text_pairs: [
          {
            source: source,
            target: target,
          },
        ],
      }),
      headers: {
        'Content-type': 'application/json; charset=UTF-8',
        ...this.authHeader(),
      },
    }).then(this.handleInvalidAuth());
  }

  async generateAnswer(
    question: string,
    genaiPrompt: string,
    references: ReferenceInfo[],
    onNextWord: (str: string) => void,
    genAiProvider?: string,
    workflowId?: string,
    onComplete?: (finalAnswer: string) => void,
    signal?: AbortSignal // <-- Add this parameter
  ) {
    let finalAnswer = ''; // Variable to accumulate the response

    try {
      const apiKey = process.env.NEXT_PUBLIC_OPENAI_API_KEY;
      let cache_access_token = null;
      try {
        cache_access_token = await temporaryCacheToken(this.getModelID());
      } catch (error) {
        console.error('Error getting cache access token:', error);
      }
      const args: any = {
        query: question,
        prompt: genaiPrompt,
        references: references.map((ref) => {
          return { text: ref.content, source: ref.sourceName, metadata: ref.metadata };
        }),
        key: apiKey,
        provider: genAiProvider,
        workflow_id: workflowId,
        cache_access_token: cache_access_token,
      };

      const uri = deploymentBaseUrl + '/llm-dispatch/generate';
      const response = await fetch(uri, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(args),
        signal: signal,
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder('utf-8');

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        const newData = decoder.decode(value, { stream: true });
        finalAnswer += newData;

        onNextWord(newData);
      }

      if (onComplete) {
        onComplete(finalAnswer);
      }
    } catch (error: unknown) {
      if (isAbortError(error)) {
        console.log('Fetch aborted');
        onNextWord(finalAnswer);
      } else {
        console.error('Generation Error:', error);
        alert('Generation Error:' + (error instanceof Error ? error.message : String(error)));
        // onNextWord('An error occurred during generation.');
      }
    }

    // Type guard to check if the error is an AbortError
    function isAbortError(error: any): error is { name: string } {
      return error && typeof error === 'object' && 'name' in error && error.name === 'AbortError';
    }
  }

  getChatHistory(provider: string): Promise<ChatMessage[]> {
    return fetch(this.url + '/get-chat-history', {
      method: 'POST',
      body: JSON.stringify({
        session_id: this.sessionId,
        provider: provider,
      }),
      headers: {
        'Content-type': 'application/json; charset=UTF-8',
        ...this.authHeader(),
      },
    })
      .then(this.handleInvalidAuth())
      .then((res) => {
        if (res.ok) {
          return res.json();
        } else {
          return res.json().then((err) => {
            throw new Error(err.detail || 'Failed to fetch chat history');
          });
        }
      })
      .then((response) => response['data']['chat_history'] as ChatMessage[])
      .catch((e) => {
        console.error('Error fetching chat history:', e);
        alert('Error fetching chat history: ' + e);
        throw e;
      });
  }

  async chat(
    textInput: string,
    provider: string,
    onNextWord: (str: string) => void,
    onComplete?: (finalResponse: string) => void,
    signal?: AbortSignal
  ): Promise<void> {
    try {
      const response = await fetch(this.url + '/chat', {
        method: 'POST',
        body: JSON.stringify({
          session_id: this.sessionId,
          user_input: textInput,
          provider: provider,
        }),
        headers: {
          'Content-type': 'application/json; charset=UTF-8',
          ...this.authHeader(),
        },
        signal,
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder('utf-8');
      let finalResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        const newData = decoder.decode(value, { stream: true });
        finalResponse += newData;

        onNextWord(newData);
      }

      if (onComplete) {
        onComplete(finalResponse);
      }
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          console.log('Chat was aborted');
        } else {
          console.error('Error in chat:', error);
          alert('Error in chat: ' + error);
        }
      } else {
        console.error('An unknown error occurred:', error);
        alert('An unknown error occurred');
      }
      throw error;
    }
  }

  setChat(provider: string): Promise<any> {
    const url = new URL(this.url + '/update-chat-settings');
    const settings = {
      provider,
    };

    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.authHeader(),
      },
      body: JSON.stringify(settings),
    })
      .then(this.handleInvalidAuth())
      .then((res) => {
        if (res.ok) {
          return res.json();
        } else {
          return res.json().then((json) => {
            throw new Error(json.message);
          });
        }
      })
      .then((data) => {
        console.log('Chat settings updated successfully:', data);
        return data;
      })
      .catch((e) => {
        console.error('Error updating chat settings:', e);
        alert('Error updating chat settings: ' + e);
        throw e;
      });
  }

  async recordImplicitFeedback(feedback: ImplicitFeecback) {
    try {
      const response = await fetch(this.url + '/implicit-feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.authHeader(),
        },
        body: JSON.stringify(feedback),
      });

      if (response.ok) {
        return response.json();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Unknown error occurred');
      }
    } catch (e) {
      console.error(e);
      alert(e);
      throw new Error('Failed to record feedback: ' + e);
    }
  }
}
