import { styled } from 'styled-components';
import UpvoteSVG from '../../assets/icons/upvote.svg';
import DownvoteSVG from '../../assets/icons/downvote.svg';
import React, { MouseEventHandler, useState } from 'react';
import { color, duration } from '../../stylingConstants';
import NotifyingClickable from './NotifyingButton';

function makeVoteButton(svg: React.FunctionComponent) {
  const StyledSVG = styled(svg)<{ $active: boolean }>`
    transition-duration: ${duration.transition};
    path {
      fill: ${(props) => (props.$active ? color.accent : 'white')};
    }

    &:hover path {
      fill: ${color.accent};
      transition-duration: ${duration.transition};
    }

    &:hover {
      cursor: pointer;
    }
  `;

  function VoteButton({ onClick }: { onClick: MouseEventHandler<any> }) {
    const [active, setActive] = useState(false);

    function handleClick(e: any) {
      if (!active) {
        setActive(true);
        onClick(e);
      }
    }

    function handleDismiss() {
      setActive(false);
    }

    return (
      <NotifyingClickable onClick={handleClick} text="Feedback received!" onDismiss={handleDismiss}>
        <StyledSVG $active={active} />
      </NotifyingClickable>
    );
  }

  return VoteButton;
}

export const UpvoteButton = makeVoteButton(UpvoteSVG);

export const DownvoteButton = makeVoteButton(DownvoteSVG);
