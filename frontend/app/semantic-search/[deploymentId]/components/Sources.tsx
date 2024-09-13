import Fuse from "fuse.js";
import React, { useContext, useEffect, useState } from "react";
import styled from "styled-components";
import {
    borderRadius,
    color,
    duration,
    fontSizes,
    shadow,
    padding,
} from "../stylingConstants";
import { ReadSourceButton, StyledArrow } from "./Reference";
import { Spacer } from "./Layout";
import { ModelService, Source } from "../modelServices";
import { ModelServiceContext } from "../Context";
import FileUploadModal from "./FileUploadModal";
import { DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface SourcesProps {
    sources: Source[];
    visible: boolean;
    setSources: (sources: Source[]) => void;
}

const Panel = styled.section`
    display: flex;
    flex-direction: column;
    padding: 10px;
    padding-bottom: 0;
    box-shadow: ${shadow.card};
    border-radius: ${borderRadius.card};
    width: 400px;
    background-color: white;
`;

const Search = styled.input`
    font-size: ${fontSizes.s};
    padding: 10px 10px 13px 10px;
    background-color: ${color.textInput};
    border-radius: ${borderRadius.textInput};
    border: none;
    height: ${fontSizes.s};
    font-family: Helvetica, Arial, sans-serif;
`;

const SourceButton = styled.section`
    font-size: ${fontSizes.s};
    font-weight: normal;
    display: flex;
    justify-content: space-between;
    text-align: left;
    align-items: center;
    margin-bottom: 10px;
    text-decoration: none;
    color: black;
    transition-duration: ${duration.transition};

    &:hover {
        color: ${color.accent};
        transition-duration: ${duration.transition};
        cursor: pointer;
    }
`;

const Scrollable = styled.section`
    max-height: 300px;
    overflow-y: scroll;
`;

export const DeleteSourceButton = styled.section`
    background-color: white;
    border: 1px solid ${color.delete};
    border-radius: ${borderRadius.smallButton};
    transition-duration: ${duration.transition};
    font-size: ${fontSizes.s};
    font-weight: normal;
    color: ${color.delete};
    width: fit-content;
    padding: ${padding.smallButton};
    margin-bottom: 10px;

    &:hover {
        background-color: ${color.delete};
        color: white;
        cursor: pointer;
    }
`;

const AddSourceButton = styled.section`
    background-color: white;
    border: 1px solid ${color.accent};
    border-radius: ${borderRadius.smallButton};
    transition-duration: ${duration.transition};
    font-size: ${fontSizes.s};
    font-weight: normal;
    color: ${color.accent};
    width: fit-content;
    padding: ${padding.smallButton};
    margin-top: 10px;
    margin-bottom: 10px;
    display: block;
    margin-left: auto;
    margin-right: auto;

    &:hover {
        background-color: ${color.accent};
        color: white;
        cursor: pointer;
    }

    &:active {
        background-color: ${color.accentDark};
    }
`;

const Divider = styled.div`
    height: 1px;
    background-color: #ccc;
`;

export default function Sources(props: SourcesProps) {
    const [fuse, setFuse] = useState<Fuse<Source> | null>(null);
    const [matches, setMatches] = useState(props.sources);
    const [open, setOpen] = useState(false);

    const modelService = useContext<ModelService | null>(ModelServiceContext);

    function formatSource(source: string) {
        const lowerSource = source.toLowerCase();
        if (
            lowerSource.endsWith(".pdf") ||
            lowerSource.endsWith(".docx") ||
            lowerSource.endsWith(".csv") ||
            lowerSource.endsWith(".txt") ||
            lowerSource.endsWith(".pptx") ||
            lowerSource.endsWith(".eml")
        ) {
            return source.split("/").pop();
        }
        return source;
    }

    useEffect(() => {
        setMatches(props.sources);
    }, [props.visible, props.sources]);

    useEffect(() => {
        setFuse(
            new Fuse(
                props.sources.map((source) => ({
                    source: formatSource(source.source)!,
                    source_id: source.source_id,
                })),
                { keys: ["source"] },
            ),
        );
    }, [props.sources]);

    function handleSearchBarChangeEvent(
        e: React.ChangeEvent<HTMLInputElement>,
    ) {
        if (e.target.value.trim() === "") {
            setMatches(props.sources);
            return;
        }
        setMatches(fuse!.search(e.target.value).map((res) => res.item));
    }

    function refreshSources() {
        modelService!.sources().then(props.setSources);
    }

    const handleAddSources = async (
        selectedFiles: FileList | null,
        s3Urls: string[],
    ) => {
        const filesArray = selectedFiles ? Array.from(selectedFiles) : [];
        await modelService!.addSources(filesArray, s3Urls);
    };

    function canReadSource(source: string): boolean {
        const lowerSource = source.toLowerCase();
        return lowerSource.endsWith(".pdf") || lowerSource.endsWith(".docx");
    }

    return (
        fuse && (
            <DropdownMenuContent 
                style={{ width: "300px", maxHeight: "300px", overflowY: "auto" }} 
                align="start" 
                side="bottom" // Ensure the dropdown opens downward
            >
                <Input
                    autoFocus
                    className="font-medium"
                    placeholder="Filter documents by name..."
                    onChange={handleSearchBarChangeEvent}
                    style={{ marginBottom: '5px' }}
                    onKeyDown={(e) => {
                        e.stopPropagation();  // Stop the event from propagating to other elements in the dropdown
                    }}
                />
                <Button style={{width: "100%", marginTop: "15px"}} onClick={() => {setOpen(true);}}>
                    Add Documents
                </Button>
                <Scrollable>
                    <Spacer $height="10px" />
                    {matches.map((source, i) => (
                        <DropdownMenuItem key={i} style={{display: "flex", paddingRight: "10px", justifyContent: "space-between"}} onClick={() =>
                        {
                            console.log("Propagated");
                            modelService!.openSource(
                                source.source,
                            )}
                        }>
                            {formatSource(source.source)}
                            <div style={{ marginLeft: "auto", marginRight: "10px" }}> {/* Add margin here */}
                                <Button
                                    className="bg-transparent hover:bg-red-500 text-red-500 hover:text-white"
                                    style={{height: "2rem", width: "2rem", border: "1px solid red"}}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        modelService!.deleteSources([
                                            source.source_id,
                                        ]);
                                        props.setSources(
                                            props.sources.filter(
                                                (x) =>
                                                    x.source_id !==
                                                    source.source_id,
                                            ),
                                        );
                                    }}
                                >✕</Button>
                            </div>
                        </DropdownMenuItem>
                    ))}
                </Scrollable>
                <FileUploadModal
                    isOpen={open}
                    handleCloseModal={() => setOpen(false)}
                    addSources={handleAddSources}
                    refreshSources={refreshSources}
                />
            </DropdownMenuContent>
        )
    );
}
