import React, { useContext } from 'react';
import NotifyingClickable from './NotifyingButton';
import Copy from '../../assets/icons/copy.svg';
import { styled } from 'styled-components';
import { color, duration } from '../../stylingConstants';
import { ModelServiceContext } from '../../Context';
import { ModelService } from '../../modelServices';

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
      onClick={() => {
        copyToClipboard();

        // TODO(Any): use update query text and uncomment below to record implicit-feedback
        // const feedback = {
        //     reference_id: 0, // TODO
        //     query_text: "", // TODO
        //     event_desc: "copy_reference_text",
        // };

        // modelService?.recordImplicitFeedback(feedback)
        //     .then(data => {
        //         console.log("Implicit feedback recorded successfully:", data)
        //     })
        //     .catch(error => {
        //         console.error("Error recording implicit feedback:", error)
        //         alert("Error recording implicit feedback:" + error)
        //     })
      }}
      text="Copied to clipboard!"
    >
      <StyledCopy />
    </NotifyingClickable>
  );
}
