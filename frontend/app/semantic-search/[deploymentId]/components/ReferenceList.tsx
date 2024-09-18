import React, { Fragment, useRef } from 'react';
import styled from 'styled-components';
import { Spacer } from './Layout';
import Reference from './Reference';
import PillButton from './buttons/PillButton';
import { fontSizes } from '../stylingConstants';
import { ModelService, ReferenceInfo } from '../modelServices';

interface ReferenceListProps {
  references: ReferenceInfo[];
  onOpen: (ref: ReferenceInfo) => void;
  onUpvote: (refId: number, content: string) => void;
  onDownvote: (refId: number, content: string) => void;
  onMore: () => void;
  showMoreButton: boolean;
  checkedIds: Set<number>;
  onCheck: (ref: number) => void;
  modelService: ModelService;
  ifGuardRailOn: boolean;
}

const Container = styled.section`
  display: flex;
  flex-direction: column;
  height: fit-content;
`;

const Header = styled.section`
  font-size: ${fontSizes.m};
  font-weight: bold;
  color: black;
`;

const ButtonContainer = styled.section`
  width: 100%;
  display: flex;
  flex-direction: row;
  justify-content: center;
`;

export default function ReferenceList({
  references,
  onOpen,
  onUpvote,
  onDownvote,
  onMore,
  showMoreButton: canRequestMore,
  checkedIds,
  onCheck,
  modelService,
  ifGuardRailOn,
}: ReferenceListProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  function handleMore() {
    buttonRef.current!.scrollIntoView();
    onMore();
  }
  return (
    <Container>
      <Header>References</Header>
      <Spacer $height="10px" />
      {references.map((ref) => (
        <Fragment key={ref.id}>
          <Reference
            info={ref}
            onOpen={() => onOpen(ref)}
            onUpvote={() => onUpvote(ref.id, ref.content)}
            onDownvote={() => onDownvote(ref.id, ref.content)}
            checked={checkedIds.has(ref.id)}
            onCheck={() => onCheck(ref.id)}
            modelService={modelService}
            ifGuardRailOn={ifGuardRailOn}
          />
          <Spacer $height="20px" />
        </Fragment>
      ))}
      <Spacer $height="10px" />
      {canRequestMore && (
        <ButtonContainer>
          <PillButton ref={buttonRef} onClick={handleMore}>
            more
          </PillButton>
        </ButtonContainer>
      )}
    </Container>
  );
}
