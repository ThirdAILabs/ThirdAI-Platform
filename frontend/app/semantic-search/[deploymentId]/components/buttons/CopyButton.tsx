import React, { useContext } from "react";
import NotifyingClickable from "./NotifyingButton";
import Copy from "../../assets/icons/copy.svg";
import { styled } from "styled-components";
import { color, duration } from "../../stylingConstants";
import { ModelServiceContext } from "../../Context";
import { ModelService } from "../../modelServices";

const StyledCopy = styled(Copy)`
    transition-duration: ${duration.transition};

    &:hover rect {
        fill: ${color.accent};
        transition-duration: ${duration.transition};
    }

    &:hover {
        cursor: pointer;
    }
`;

export default function CopyButton({ toCopy }: { toCopy: string }) {
    const modelService = useContext<ModelService | null>(ModelServiceContext);

    function copyToClipboard() {
        navigator.clipboard.writeText(toCopy);
    }
    return (
        <NotifyingClickable
            onClick={()=>{
                copyToClipboard()

                // Create a telemetry event
                const event = {
                    UserAction: 'Copy',
                    UIComponent: 'CopyButton',
                    UI: 'Clipboard',
                    data: {
                        copiedText: toCopy
                    }
                };

                // Record the event
                modelService?.recordEvent(event)
                    .then(data => {
                        console.log("Event recorded successfully:", data);
                    })
                    .catch(error => {
                        console.error("Error recording event:", error);
                    });
                    }}
                    text="Copied to clipboard!"
        >
            <StyledCopy />
        </NotifyingClickable>
    );
}
