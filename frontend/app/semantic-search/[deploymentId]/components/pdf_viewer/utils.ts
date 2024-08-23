import { Box, Chunk, DocChunks, Point } from "./interfaces";

export function pointInBox(point: Point, box: Box, tolerance: number) {
    const { page: pointPage, x, y } = point;
    const {
        page: boxPage,
        borders: { left, right, top, bottom },
    } = box;
    return (
        pointPage === boxPage &&
        x >= left - tolerance &&
        x <= right + tolerance &&
        y >= top - tolerance &&
        y <= bottom + tolerance
    );
}

function findMatchingBoxIdx(point: Point, chunk: Chunk) {
    let idx = 0;
    for (const box of chunk.boxes) {
        if (pointInBox(point, box, /* tolerance= */ 5)) {
            break;
        }
        idx++;
    }
    return idx;
}

function distanceFromMiddleOfChunk(boxIdx: number, chunk: Chunk) {
    return Math.abs(chunk.boxes.length / 2 - boxIdx);
}

export function getChunk(point: Point, docChunks: DocChunks): Chunk | null {
    const pageChunks = docChunks[point.page];
    type IdxAndChunk = [number, Chunk];
    const matches = pageChunks
        .map(
            (chunk) => [findMatchingBoxIdx(point, chunk), chunk] as IdxAndChunk,
        )
        .filter(([idx, chunk]) => idx < chunk.boxes.length)
        .sort(([idx1, chunk1], [idx2, chunk2]) => {
            // Prioritize matches that are closer to the middle of the chunk.
            return (
                distanceFromMiddleOfChunk(idx1, chunk1) -
                distanceFromMiddleOfChunk(idx2, chunk2)
            );
        });
    // Get first element of matches, then get the chunk part of the pair.
    return matches.length > 0 ? matches[0][1] : null;
}
