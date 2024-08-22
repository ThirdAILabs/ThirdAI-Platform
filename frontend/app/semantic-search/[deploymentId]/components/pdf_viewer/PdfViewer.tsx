"use client"

import React, { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import styled from "styled-components";
import {
    borderRadius,
    color,
    duration,
    fontSizes,
    padding,
    shadow,
} from "../../stylingConstants";
import { Spacer } from "../Layout";
import { Borders, Chunk, DocChunks, Point } from "./interfaces";
import { getChunk } from "./utils";

// @ts-ignore
import * as pdfjsLib from "pdfjs-dist/build/pdf";
// @ts-ignore
import pdfjsWorker from "pdfjs-dist/build/pdf.worker.entry";
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

const Container = styled.section`
    display: flex;
    position: relative;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    justify-content: center;
    background-color: grey;
    overflow-x: hidden;
    overflow-y: hidden;
    border-radius: ${borderRadius.card};
    box-shadow: ${shadow.button};
`;

const ScrollableContainer = styled.section`
    display: flex;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    justify-content: center;
    background-color: grey;
    overflow-x: scroll;
    overflow-y: scroll;
`;

const Title = styled.section`
    display: block;
    position: absolute;
    width: 100%;
    font-size: ${fontSizes.m};
    font-weight: bold;
    display: flex;
    text-align: left;
    color: white;
    text-shadow: ${shadow.button};
    background-image: linear-gradient(#00000050, #00000000);
    padding: 25px;
    z-index: 10;
    border-radius: ${borderRadius.card} ${borderRadius.card} 0 0;
    box-sizing: border-box;
    pointer-events: none; /* Makes the layer click-through */
`;

const DocumentWrapper = styled.section`
    margin: 50px;
`;

const PageContainer = styled.section`
    margin-top: 10px;
    margin-bottom: 10px;
    box-shadow: ${shadow.button};
`;

const CloseButtonWrapper = styled.section`
    margin: 15px;
    position: absolute;
    right: 0;
    z-index: 200;
`;

const BottomRowButtonsWrapper = styled.section`
    margin: 15px;
    position: absolute;
    bottom: 0;
    z-index: 200;
    display: flex;
`;

const CircularButton = styled.button`
    font-size: 24px; /* Adjust size as needed */
    font-weight: bold;
    text-shadow: ${shadow.button};
    color: #fff; /* Color of the 'X' */
    background-color: transparent;
    border: none;
    cursor: pointer;
    outline: none;
    height: 45px;
    width: 45px;
    padding-bottom: 2px;
    border-radius: 50%; /* Optional: for round shape */
    display: inline-block;
    text-align: center;
    line-height: 1; /* Ensures proper vertical alignment */
    transition-duration: ${duration.transition};
    background-color: rgba(0, 0, 0, 0.2); /* Slight shade on hover */
    &:hover {
        background-color: rgba(0, 0, 0, 0.4); /* Slight shade on hover */
    }
    &:focus {
        box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.5);
    }
`;

interface PdfViewerProps {
    name: string;
    src: string;
    chunks: DocChunks;
    initialChunk: Chunk;
    onSelect: (chunk: Chunk | null) => void;
    onClose: () => void;
}

export default function PdfViewer(props: PdfViewerProps) {
    const [pageWidth, setPageWidth] = useState<number>(window.outerWidth);
    const [zoomScale, setZoomScale] = useState(1.0);
    const [numPages, setNumPages] = useState<number>();
    const [numPagesReady, setNumPagesReady] = useState<number>(0);
    const [chunk, setChunk] = useState<Chunk | null>(props.initialChunk);
    const scrollableComponentRef = useRef<HTMLElement>(null);
    const undoerRefs = useRef<(string | null)[]>([]);
    const canvasRefs = useRef<HTMLCanvasElement[]>([]);
    const origDimRefs = useRef<[number, number][]>([]);
    const pendingInitialScrollRef = useRef<boolean>(true);

    useEffect(() => {
        window.addEventListener("resize", () => {
            setPageWidth(window.outerWidth);
        });
    }, []);

    function reload() {
        canvasRefs.current = Array(numPages);
        undoerRefs.current = Array(numPages);
        origDimRefs.current = Array(numPages);
        pendingInitialScrollRef.current = true;
        setNumPagesReady(0);
    }

    function onDocumentLoadSuccess({ numPages }: { numPages: number }): void {
        setNumPages(numPages);
        reload();
    }

    function pageClickHandler(page: number, pageCallback: any) {
        const pageCanvas = canvasRefs.current[page];
        const origWidth = pageCallback.originalWidth;
        const origHeight = pageCallback.originalHeight;
        origDimRefs.current[page] = [origWidth, origHeight];

        return (event: MouseEvent) => {
            const pageCanvasRect = pageCanvas.getBoundingClientRect();
            const horizontalScaler = origWidth / pageCanvasRect.width;
            const verticalScaler = origHeight / pageCanvasRect.height;
            const point: Point = {
                page,
                x: (event.clientX - pageCanvasRect.left) * horizontalScaler,
                y: (event.clientY - pageCanvasRect.top) * verticalScaler,
            };
            console.log(point);
            const chunk = getChunk(point, props.chunks);
            setChunk(chunk);
            props.onSelect(chunk);
        };
    }

    const onRenderSuccess = (page: number) => (event: any) => {
        canvasRefs.current[page].style.position = "relative";
        canvasRefs.current[page].addEventListener(
            "click",
            pageClickHandler(page, event),
        );
        setNumPagesReady((prev) => prev + 1);
    };

    function zoomOut() {
        setZoomScale((curZoomScale) => Math.max(0.1, curZoomScale - 0.1));
        reload();
    }

    function zoomIn() {
        setZoomScale((curZoomScale) => Math.min(2.0, curZoomScale + 0.1));
        reload();
    }

    interface PageActions {
        highlight: Borders[] | null;
        reset: boolean;
    }

    function getActionItems(undoers: (string | null)[], chunk: Chunk | null) {
        let pageToActions: (PageActions | null)[] = Array(numPages);
        undoers.forEach((cache, pageIdx) => {
            if (cache) {
                pageToActions[pageIdx] = {
                    highlight: null,
                    reset: true,
                };
            }
        });
        if (chunk === null) {
            return pageToActions;
        }
        for (const { page, borders } of chunk.boxes) {
            if (!pageToActions[page]) {
                pageToActions[page] = { highlight: null, reset: false };
            }
            if (!pageToActions[page].highlight) {
                pageToActions[page].highlight = [];
            }
            pageToActions[page].highlight.push(borders);
        }
        return pageToActions;
    }

    function scaleForCanvas(origBox: Borders, pageIdx: number): Borders {
        const rect = canvasRefs.current[pageIdx].getBoundingClientRect();
        const [origWidth, origHeight] = origDimRefs.current[pageIdx];
        const horizontalScale = rect.width / origWidth;
        const verticalScale = rect.height / origHeight;
        return {
            left: origBox.left * horizontalScale,
            right: origBox.right * horizontalScale,
            top: origBox.top * verticalScale,
            bottom: origBox.bottom * verticalScale,
        };
    }

    function highlightCurrentChunk() {
        if (numPagesReady !== numPages || !chunk) {
            return;
        }

        const actionItems = getActionItems(undoerRefs.current, chunk);

        actionItems.forEach((actions, actionPageIdx) => {
            if (actions === null) {
                return;
            }
            function highlightIfNeeded() {
                if (!actions?.highlight) {
                    return;
                }
                undoerRefs.current[actionPageIdx] =
                    undoerRefs.current[actionPageIdx] ??
                    canvasRefs.current[actionPageIdx].toDataURL();
                const canvas = canvasRefs.current[actionPageIdx];
                const ctx = canvas.getContext("2d");
                ctx!.fillStyle = color.accentLight + "20";
                for (const origBox of actions.highlight) {
                    const box = scaleForCanvas(origBox, actionPageIdx);
                    ctx!.fillRect(
                        box.left * 2,
                        box.top * 2,
                        (box.right - box.left) * 2,
                        (box.bottom - box.top) * 2,
                    );
                }
            }

            if (actions.reset) {
                const ctx = canvasRefs.current[actionPageIdx].getContext("2d");
                const img = new Image();
                img.onload = () => {
                    ctx!.drawImage(img, 0, 0);
                    highlightIfNeeded();
                };
                img.src = undoerRefs.current[actionPageIdx]!;
            } else {
                highlightIfNeeded();
            }
        });
        if (numPagesReady === numPages && chunk) {
        }
    }

    useEffect(highlightCurrentChunk, [numPagesReady, chunk]);

    function scrollToHighlightOnLoad() {
        if (
            pendingInitialScrollRef.current &&
            numPagesReady === numPages &&
            chunk
        ) {
            const { page, borders } = chunk.boxes[0];
            scrollableComponentRef.current!.scrollTop =
                scrollableComponentRef.current!.scrollTop +
                canvasRefs.current[page].getBoundingClientRect().top +
                scaleForCanvas(borders, page).top -
                200;
            pendingInitialScrollRef.current = false;
        }
    }

    useEffect(scrollToHighlightOnLoad, [numPagesReady]);

    return (
        <Container>
            <Title>{props.name.split("/").pop()}</Title>
            <CloseButtonWrapper>
                <CircularButton onClick={props.onClose}>×</CircularButton>
            </CloseButtonWrapper>
            <BottomRowButtonsWrapper>
                <CircularButton onClick={zoomOut}>-</CircularButton>
                <Spacer $width="10px" />
                <CircularButton onClick={zoomIn}>+</CircularButton>
            </BottomRowButtonsWrapper>
            <ScrollableContainer ref={scrollableComponentRef}>
                <DocumentWrapper>
                    <Document
                        file={props.src}
                        onLoadSuccess={onDocumentLoadSuccess}
                        onLoadError={console.log}
                    >
                        {new Array(numPages).fill(null).map((_, i) => (
                            <PageContainer key={i}>
                                <Page
                                    pageNumber={i + 1}
                                    renderTextLayer={false}
                                    renderAnnotationLayer={false}
                                    width={0.6 * zoomScale * pageWidth}
                                    canvasRef={(elem) => {
                                        canvasRefs.current[i] = elem!;
                                    }}
                                    onRenderSuccess={onRenderSuccess(i)}
                                />
                            </PageContainer>
                        ))}
                    </Document>
                </DocumentWrapper>
            </ScrollableContainer>
        </Container>
    );
}
