export interface Point {
    page: number;
    x: number;
    y: number;
}

export interface Borders {
    left: number;
    right: number;
    top: number;
    bottom: number;
}

export interface Box {
    page: number;
    borders: Borders;
}

export interface Chunk {
    id: number;
    text: string;
    boxes: Box[];
}

export type PageChunks = Chunk[];

export type DocChunks = PageChunks[];
