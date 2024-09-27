import { genaiQuery } from './genai';
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

export interface SearchResult {
  queryId: string;
  query: string;
  references: ReferenceInfo[];
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
  sessionId: string;
  authToken: string | null;
  tokenModelUrl: string;

  constructor(url: string, tokenModelUrl: string, sessionId: string) {
    this.url = url;
    this.sessionId = sessionId;
    this.tokenModelUrl = tokenModelUrl;
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
        console.log(data);
        return data;
      })
      .catch((e) => {
        return [];
      });
  }

  async piiDetect(query: string): Promise<any> {
    const url = new URL(this.tokenModelUrl + '/predict');

    const baseParams = { query: query, top_k: 1 };

    return fetch(url, {
      method: 'POST',
      headers: {
        ...this.authHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(baseParams),
    })
      .then(this.handleInvalidAuth())
      .then((response) => {
        // console.log('response', response)
        if (response.ok) {
          return response.json();
        } else {
          return response.json().then((err) => {
            throw new Error(err.detail || 'Unknown error occurred');
          });
        }
      })
      .then(({ data }) => {
        // console.log(data);
        return data as PIIDetectionResult;
      })
      .catch((e) => {
        console.error(e);
        alert(e);
        throw new Error('Failed to detect PII');
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
    const documentData: object[] = [];

    // Append local files to formData and documentData
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
      const extension = files[i].name.split('.').pop();
      documentData.push({
        document_type: extension!.toUpperCase(),
        path: files[i].name,
        location: 'local',
      });
    }

    // Append S3 URLs to documentData
    for (let i = 0; i < s3Urls.length; i++) {
      const url = s3Urls[i];
      const extension = url.split('.').pop();
      documentData.push({
        document_type: extension ? extension.toUpperCase() : 'URL',
        path: url,
        location: 's3',
      });
    }

    formData.append('documents', JSON.stringify(documentData));
    const url = new URL(this.url + '/insert');

    return fetch(url, {
      method: 'POST',
      body: formData,
      headers: {
        ...this.authHeader(),
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
    const url = new URL(this.url + '/predict');

    // TODO(Geordie): Accept a "timeout" / "longer than expected" callback.
    // E.g. if the query takes too long, then we can display a message
    // saying that they should check the url, or maybe it's just taking a
    // while.

    const baseParams = { query: queryText, top_k: topK };
    const ndbParams = { constraints: {} };

    return fetch(url, {
      method: 'POST',
      headers: {
        ...this.authHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ base_params: baseParams, ndb_params: ndbParams }),
    })
      .then(this.handleInvalidAuth())
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
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
        };
        return searchResults;
      })
      .catch((e) => {
        console.log(e);
        return null;
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
    onComplete?: (finalAnswer: string) => void
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
        query: genaiQuery(question, references, genaiPrompt),
        key: apiKey,
        provider: genAiProvider,
        workflow_id: workflowId,
        original_query: question,
        cache_access_token: cache_access_token,
      };

      const uri = deploymentBaseUrl + '/llm-dispatch/generate';
      const response = await fetch(uri, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(args),
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
    } catch (error) {
      console.error('Generation Error:', error);
      alert('Generation Error:' + error);
      onNextWord('An error occurred during generation.');
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

  chat(textInput: string, provider: string): Promise<ChatResponse> {
    return fetch(this.url + '/chat', {
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
    })
      .then(this.handleInvalidAuth())
      .then((res) => {
        if (res.ok) {
          return res.json();
        } else {
          return res.json().then((err) => {
            throw new Error(err.detail || 'Failed to fetch chat response');
          });
        }
      })
      .then((response) => response['data'] as ChatResponse)
      .catch((e) => {
        console.error('Error in chat:', e);
        alert('Error in chat: ' + e);
        throw e;
      });
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
