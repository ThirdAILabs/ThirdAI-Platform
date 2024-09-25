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

export default function CopyButton({
  toCopy,
  referenceID,
  queryText,
}: {
  toCopy: string;
  referenceID: number;
  queryText: string;
}) {
  const modelService = useContext<ModelService | null>(ModelServiceContext);

  function copyToClipboard() {
    navigator.clipboard.writeText(toCopy);
  }
  return (
    <NotifyingClickable
      onClick={() => {
        copyToClipboard();

        // use update query text and uncomment below to record implicit-feedback
        const feedback = {
          reference_id: referenceID,
          reference_rank: 0, // TODO: fill with exact rank
          query_text: queryText,
          event_desc: 'copy_reference_text',
        };

        console.log('feedback logged', feedback);

        modelService
          ?.recordImplicitFeedback(feedback)
          .then((data) => {
            console.log('Implicit feedback recorded successfully:', data);
          })
          .catch((error) => {
            console.error('Error recording implicit feedback:', error);
            alert('Error recording implicit feedback:' + error);
          });
      }}
      text="Copied to clipboard!"
    >
      <StyledCopy />
    </NotifyingClickable>
  );
}
