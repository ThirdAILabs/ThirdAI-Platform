import { genaiQuery } from "./genai";
import { Box, Chunk, DocChunks } from "./components/pdf_viewer/interfaces";

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

export interface ModelService {
    isUserModel: () => boolean;
    sources: () => Promise<Source[]>;
    saveModel: (override: boolean, model_name?: string) => Promise<any>;
    addSources: (files: File[], s3Urls: string[]) => Promise<any>;
    deleteSources: (sourceIDs: string[]) => Promise<any>;
    predict: (
        queryText: string,
        topK: number,
        queryId?: string,
    ) => Promise<SearchResult | null>;
    openSource: (source: string) => void;
    openReferenceSource: (reference: ReferenceInfo) => void;
    getPdfInfo: (reference: ReferenceInfo) => Promise<PdfInfo>;
    upvote: (
        queryId: string,
        queryText: string,
        referenceId: number,
        referenceText: string,
    ) => Promise<any>;
    downvote: (
        queryId: string,
        queryText: string,
        referenceId: number,
        referenceText: string,
    ) => Promise<any>;
    qna: (question: string, answer: string) => Promise<any>;
    associate: (source: string, target: string) => Promise<any>;
    generateAnswer: (
        question: string,
        genaiPrompt: string,
        references: ReferenceInfo[],
        websocketRef: React.MutableRefObject<WebSocket>,
        onNextWord: (str: string) => void,
    ) => Promise<void>;
    authHeader: () => Record<string, string>;
    handleInvalidAuth: () => void;
    getChatHistory: () => Promise<ChatMessage[]>;
    chat: (textInput: string) => Promise<ChatResponse>;
    piiDetect(query: string): Promise<PIIDetectionResult>;
    updatePiiSettings(token_model_id: string, llm_guardrail: boolean): Promise<any>
}

function sourceName(ref: ReferenceJson) {
    if (ref.source.endsWith(".pdf") || ref.source.endsWith(".docx")) {
        return ref.source.split("/").at(-1);
    }
    if ("title" in ref.metadata) {
        return ref.metadata["title"];
    }
    return ref.source;
}

function startAndEnd(text: string, n_words: number = 2) {
    const trimmed = text.replace(/^[^a-z\d]*|[^a-z\d]*$/gi, "");

    let startSpaces = 0;
    let startEnd = 0;
    for (; startEnd < trimmed.length; startEnd++) {
        if (trimmed[startEnd] === " ") {
            startSpaces++;
        }
        if (startSpaces === n_words) {
            break;
        }
    }

    let endSpaces = 0;
    let endStart = trimmed.length - 1;
    for (; endStart >= 0; endStart--) {
        if (trimmed[endStart] === " ") {
            endSpaces++;
        }
        if (endSpaces === n_words) {
            break;
        }
    }

    return [trimmed.substring(0, startEnd), trimmed.substring(endStart + 1)];
}

function handleInvalidAuth(modelService: ModelService) {
    return (response: Response) => {
        if (response.status == 401) {
            modelService.handleInvalidAuth();
        }
        return response;
    };
}

export class GlobalModelService implements ModelService {
    url: string;
    wsUrl: string;
    sessionId: string;

    constructor(url: string, sessionId: string) {
        this.url = url;
        this.wsUrl = `${window.location.protocol}//${window.location.host}`.replace("http", "ws");
        this.sessionId = sessionId;
    }

    isUserModel(): boolean {
        return false;
    }

    authHeader(): Record<string, string> {
        return {};
    }

    handleInvalidAuth(): void {}

    async sources(): Promise<Source[]> {
        const url = new URL(this.url + "/sources");
        return fetch(url, { headers: this.authHeader() })
            .then(handleInvalidAuth(this))
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

    async updatePiiSettings( token_model_id: string, llm_guardrail: boolean ): Promise<any> {
        const url = new URL(this.url + "/update-pii-settings");
        url.searchParams.append('token_model_id', token_model_id);
        url.searchParams.append('llm_guardrail', String(llm_guardrail));

        const response = await fetch(url.toString(), {
            method: "POST",
            headers: {
                ...this.authHeader(),
                "Content-Type": "application/json",
            }
        });
    
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Unknown error occurred");
        }
    
        return response.json();
    }

    async piiDetect(query: string): Promise<any> {
        const url = new URL(this.url + "/pii-detect");
        url.searchParams.append('query', query);
        
        return fetch(url, {
            method: "POST",
            headers: {
                ...this.authHeader(),
                "Content-Type": "application/json",
            }
        })
            .then(handleInvalidAuth(this))
            .then((response) => {
                console.log('response', response)
                if (response.ok) {
                    return response.json();
                } else {
                    return response.json().then((err) => {
                        throw new Error(err.detail || "Unknown error occurred");
                    });
                }
            })
            .then(({ data }) => {
                console.log(data);
                return data as PIIDetectionResult;
            })
            .catch((e) => {
                console.error(e);
                throw new Error('Failed to detect PII');
            });
    }

    async saveModel(override: boolean, model_name?: string): Promise<any> {
        const url = new URL(this.url + "/save");
        const payload = {
            override,
            model_name: model_name || null,
        };

        return fetch(url, {
            method: "POST",
            body: JSON.stringify(payload),
            headers: {
                ...this.authHeader(),
                "Content-Type": "application/json",
            },
        })
            .then(handleInvalidAuth(this))
            .then((response) => {
                if (response.ok) {
                    return response.json();
                }
                return response.json().then((json) => {
                    throw new Error(json.message);
                });
            })
            .then((data) => {
                console.log("Model saved successfully:", data);
                return data;
            })
            .catch((e) => {
                console.error("Error saving model:", e);
                throw e;
            });
    }

    async addSources(files: File[], s3Urls: string[]): Promise<any> {
        const formData = new FormData();
        const documentData: object[] = [];

        // Append local files to formData and documentData
        for (let i = 0; i < files.length; i++) {
            formData.append("files", files[i]);
            const extension = files[i].name.split(".").pop();
            documentData.push({
                document_type: extension.toUpperCase(),
                path: files[i].name,
                location: "local",
            });
        }

        // Append S3 URLs to documentData
        for (let i = 0; i < s3Urls.length; i++) {
            const url = s3Urls[i];
            const extension = url.split(".").pop();
            documentData.push({
                document_type: extension ? extension.toUpperCase() : "URL",
                path: url,
                location: "s3",
            });
        }

        formData.append("documents", JSON.stringify(documentData));
        const url = new URL(this.url + "/insert");

        return fetch(url, {
            method: "POST",
            body: formData,
            headers: {
                ...this.authHeader(),
            },
        })
            .then(handleInvalidAuth(this))
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
        const url = new URL(this.url + "/delete");
        return fetch(url, {
            method: "POST",
            body: JSON.stringify({
                source_ids: sourceIDs,
            }),
            headers: {
                ...this.authHeader(),
                "Content-Type": "application/json",
            },
        })
            .then(handleInvalidAuth(this))
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

    async predict(
        queryText: string,
        topK: number,
        queryId?: string,
    ): Promise<SearchResult | null> {
        const url = new URL(this.url + "/predict");

        // TODO(Geordie): Accept a "timeout" / "longer than expected" callback.
        // E.g. if the query takes too long, then we can display a message
        // saying that they should check the url, or maybe it's just taking a
        // while.

        const baseParams = { query: queryText, top_k: topK };
        const ndbParams = { constraints: {} };

        return fetch(url, { 
                method: "POST", 
                headers: {
                    ...this.authHeader(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ base_params: baseParams, ndb_params: ndbParams })
            })
            .then(handleInvalidAuth(this))
            .then((response) => {
                if (response.ok) {
                    return response.json();
                }
            })
            .then(({ data }) => {
                const searchResults: SearchResult = {
                    queryId: queryId ?? data["query_id"],
                    query: data["query_text"],
                    references: data["references"].map((ref: any) => ({
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
        const blobUrl = new URL(this.url + "/pdf-blob");
        blobUrl.searchParams.append("source", reference.sourceURL.toString());
        const blobPromise = fetch(blobUrl, { headers: this.authHeader() })
            .then(handleInvalidAuth(this))
            .then((res) => res.arrayBuffer())
            .then((data) => {
                var file = new Blob([data], { type: "application/pdf" });
                return URL.createObjectURL(file);
            });

        const chunkUrl = new URL(this.url + "/pdf-chunks");
        chunkUrl.searchParams.append("reference_id", reference.id.toString());
        let highlighted: Chunk = null;
        const chunkPromise = fetch(chunkUrl, { headers: this.authHeader() })
            .then(handleInvalidAuth(this))
            .then((res) => res.json())
            .then(({ data }) => {
                const filename = data.filename as string;
                const ids = data.id as number[];
                const texts = data.text as string[];
                const boxes = data.boxes as [
                    number,
                    [number, number, number, number],
                ][][];

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
                return [filename, docChunks, highlighted] as [
                    string,
                    DocChunks,
                    Chunk,
                ];
            });

        return Promise.all([blobPromise, chunkPromise]).then(
            ([source, [filename, docChunks, highlighted]]) => ({
                filename,
                source,
                docChunks,
                highlighted,
            }),
        );
    }

    openHighlightedPDF(reference: ReferenceInfo) {
        const url = new URL(this.url + "/highlighted-pdf");
        url.searchParams.append("reference_id", reference.id.toString());
        fetch(url, { headers: this.authHeader() })
            .then(handleInvalidAuth(this))
            .then((res) => res.arrayBuffer())
            .then((data) => {
                var file = new Blob([data], { type: "application/pdf" });
                var fileURL = URL.createObjectURL(file);
                window.open(
                    fileURL + `#page=${reference.metadata["page"] + 1}`,
                );
            })
            .catch(console.log);
    }

    openPDF(source: string) {
        const url = new URL(this.url + "/pdf-blob");
        url.searchParams.append("source", source.toString());
        fetch(url, { headers: this.authHeader() })
            .then(handleInvalidAuth(this))
            .then((res) => res.arrayBuffer())
            .then((data) => {
                var file = new Blob([data], { type: "application/pdf" });
                var fileURL = URL.createObjectURL(file);
                window.open(fileURL);
            })
            .catch(console.log);
    }

    openHighlightedURL(reference: ReferenceInfo) {
        const [start, end] = startAndEnd(reference.content);
        const highlightedSourceURL =
            reference.sourceURL + "#:~:text=" + start + "," + end;
        window.open(highlightedSourceURL);
    }

    openDOCX(source: string) {
        const viewingBaseUrl = "http://docs.google.com/gview?url=";
        const path = source.substring(source.search("/documents"));
        window.open(viewingBaseUrl + this.url + path);
    }

    openReferenceSource(reference: ReferenceInfo): void {
        if (reference.sourceURL.toLowerCase().endsWith(".pdf")) {
            this.openHighlightedPDF(reference);
        } else if (reference.sourceURL.toLowerCase().endsWith(".docx")) {
            this.openDOCX(reference.sourceURL);
        } else {
            this.openHighlightedURL(reference);
        }
    }

    openSource(source: string): void {
        if (source.toLowerCase().endsWith(".pdf")) {
            this.openPDF(source);
        } else if (source.toLowerCase().endsWith(".docx")) {
            this.openDOCX(source);
        } else {
            window.open(source);
        }
    }

    async upvote(
        queryId: string,
        queryText: string,
        referenceId: number,
        referenceText: string,
    ): Promise<any> {
        return fetch(this.url + "/upvote", {
            method: "POST",
            body: JSON.stringify({
                text_id_pairs: [
                    {
                        query_text: queryText,
                        reference_id: referenceId,
                    },
                ],
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
                ...this.authHeader(),
            },
        }).then(handleInvalidAuth(this));
    }

    async downvote(
        queryId: string,
        queryText: string,
        referenceId: number,
        referenceText: string,
    ): Promise<any> {
        return fetch(this.url + "/downvote", {
            method: "POST",
            body: JSON.stringify({
                text_id_pairs: [
                    {
                        query_text: queryText,
                        reference_id: referenceId,
                    },
                ],
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
                ...this.authHeader(),
            },
        }).then(handleInvalidAuth(this));
    }

    async qna(question: string, answer: string): Promise<any> {
        return fetch(this.url + "/qna", {
            method: "POST",
            body: JSON.stringify({
                qna_pairs: [
                    {
                        question: question,
                        answer: answer,
                    },
                ],
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
                ...this.authHeader(),
            },
        }).then(handleInvalidAuth(this));
    }

    async associate(source: string, target: string): Promise<any> {
        return fetch(this.url + "/associate", {
            method: "POST",
            body: JSON.stringify({
                text_pairs: [
                    {
                        source: source,
                        target: target,
                    },
                ],
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
                ...this.authHeader(),
            },
        }).then(handleInvalidAuth(this));
    }

    async generateAnswer(
        question: string,
        genaiPrompt: string,
        references: ReferenceInfo[],
        websocketRef: React.MutableRefObject<WebSocket>,
        onNextWord: (str: string) => void,
    ) {
        const args = {
            query: genaiQuery(question, references, genaiPrompt),
            key: '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' // fill in openai key
        };

        const uri = this.wsUrl + "/generate";
        websocketRef.current = new WebSocket(uri);

        websocketRef.current.onopen = async function (event) {
            websocketRef.current.send(JSON.stringify(args));
        };

        websocketRef.current.onmessage = function (event) {
            const response = JSON.parse(event.data);
            if (response["status"] === "error") {
                onNextWord(response["detail"]);
            }
            if (response["status"] === "success") {
                onNextWord(response["content"]);
            }
            if (response["end_of_stream"]) {
                websocketRef.current.close();
            }
        };

        websocketRef.current.onerror = function (error) {
            console.error("Generation Error:", error);
        };

        websocketRef.current.onclose = function (event) {
            if (event.wasClean) {
                console.log(
                    `Closed cleanly, code=${event.code}, reason=${event.reason}`,
                );
            } else {
                console.error(`Connection died`);
            }
        };
    }

    getChatHistory(): Promise<ChatMessage[]> {
        return fetch(this.url + "/get-chat-history", {
            method: "POST",
            body: JSON.stringify({ session_id: this.sessionId }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
                ...this.authHeader(),
            },
        })
            .then(handleInvalidAuth(this))
            .then((res) => res.json())
            .then(
                (response) => response["data"]["chat_history"] as ChatMessage[],
            );
    }

    chat(textInput: string): Promise<ChatResponse> {
        return fetch(this.url + "/chat", {
            method: "POST",
            body: JSON.stringify({
                session_id: this.sessionId,
                user_input: textInput,
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
                ...this.authHeader(),
            },
        })
            .then(handleInvalidAuth(this))
            .then((res) => res.json())
            .then((response) => response["data"] as ChatResponse);
    }
}

export class UserModelService extends GlobalModelService {
    authToken: string;

    constructor(url: string, sessionId: string, authToken: string) {
        super(url, sessionId);
        this.authToken = authToken;
    }

    authHeader(): Record<string, string> {
        return {
            Authorization: `Bearer ${this.authToken}`,
            "Cache-Control": "no-cache",
        };
    }

    handleInvalidAuth(): void {
        alert(
            "You do not have the correct permissions. Please sign into Model Bazaar with the correct credentials.",
        );
        // TODO(Geordie): Handle invalid auth by redirecting to model bazaar login page.
    }

    isUserModel(): boolean {
        return true;
    }
}
