import React, { MouseEventHandler, useContext, useEffect, useState } from 'react';
import styled from 'styled-components';
import { borderRadius, color, fontSizes, padding, shadow, duration } from '../stylingConstants';
import Arrow from '../assets/icons/read_source_arrow.svg';
import CopyButton from './buttons/CopyButton';
import { Spacer } from './Layout';
import { DownvoteButton, UpvoteButton } from './buttons/VoteButtons';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ModelServiceContext } from '../Context';
import { ModelService, ReferenceInfo, PIIDetectionResult } from '../modelServices';

const Stripe = styled.section`
  background: ${color.accent};
  height: auto;
  width: 25px;
  border-radius: ${borderRadius.card} 0 0 ${borderRadius.card};
`;

const TextContainer = styled.section`
  padding: ${padding.card};
  color: black;
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
`;

const Header = styled.a`
  font-size: ${fontSizes.m};
  font-weight: bold;
  display: flex;
  text-align: left;
  align-items: center;
  margin-bottom: 10px;
  text-decoration: none;
  color: black;
  transition-duration: ${duration.transition};
  width: fit-content;

  &:hover {
    color: ${color.accent};
    transition-duration: ${duration.transition};
    cursor: pointer;
  }
`;

export const ReadSourceButton = styled.section`
  background-color: white;
  border: 1px solid ${color.accent};
  border-radius: ${borderRadius.smallButton};
  transition-duration: ${duration.transition};
  font-size: ${fontSizes.s};
  font-weight: normal;
  color: ${color.accent};
  width: fit-content;
  padding: ${padding.smallButton};
  display: flex;
  flex-direction: row;

  ${Header}:hover & {
    background-color: ${color.accent};
    color: white;
  }
`;

export const StyledArrow = styled(Arrow)`
  transition-duration: ${duration.transition};
  margin-left: 5px;
  margin-right: 2px;
  margin-top: 5px;

  ${Header}:hover & path {
    fill: white;
    transition-duration: ${duration.transition};
  }
`;

const Content = styled.section`
  font-size: ${fontSizes.s};
  text-align: left;
`;

const ButtonsContainer = styled.section`
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: ${padding.card};
`;

const VoteButtonsContainer = styled.section`
  display: flex;
  flex-direction: column;
`;

interface ReferenceProps {
  query: string;
  info: ReferenceInfo;
  onOpen: MouseEventHandler<any>;
  onUpvote: MouseEventHandler<any>;
  onDownvote: MouseEventHandler<any>;
  checked: boolean;
  onCheck: () => void;
  modelService: ModelService;
  piiMap: object | null;
}


interface TokenTag {
  token: string
  tag: string
}

function getTokensAndTags(text: string, piiMap: object): TokenTag[] {
  const tokens = text.replaceAll(/\[([A-Z]+) (#\d+)\]/gi, '$1<pii>$2').split(' ');

  var token_tags: TokenTag[] = [];

  for (const token of tokens) {
    if (token.includes("<pii>")) {
      const items = token.split("<pii>");
      const tag = items[0]
      const label = `[${tag} ${items[1]}]`

      if (tag in piiMap) {
        if (label in piiMap[tag]) {
          token_tags.push({ token: piiMap[tag][label], tag: tag })
        } else {
          token_tags.push({ token: "[UNKNOWN]", tag: "" })
        }
      } else {
        token_tags.push({ token: "[UNKNOWN]", tag: "" })
      }
    } else {
      token_tags.push({ token: token, tag: "" })
    }
  }
  console.log(text)
  console.log(token_tags)

  return token_tags;
}

export default function Reference({
  query,
  info,
  onOpen,
  onUpvote,
  onDownvote,
  checked,
  onCheck,
  modelService,
  piiMap,
}: ReferenceProps) {
  const [opacity, setOpacity] = useState('0');
  useEffect(() => setOpacity('100%'), []);

  const isReadableSource = (source: string): boolean => {
    const lowerSource = source.toLowerCase();
    return lowerSource.endsWith('.pdf') || lowerSource.endsWith('.docx');
  };

  const labels = [
    {
      id: 1,
      name: 'PHONENUMBER',
      color: 'blue',
      amount: '217,323',
      checked: true,
      description:
        'The format of a US phone number is (XXX) XXX-XXXX, where "X" represents a digit from 0 to 9. It consists of a three-digit area code, followed by a three-digit exchange code, and a four-digit line number.',
    },
    {
      id: 2,
      name: 'SSN',
      color: 'orange',
      amount: '8,979',
      checked: true,
      description:
        'The format of a US Social Security Number (SSN) is XXX-XX-XXXX, where "X" represents a digit from 0 to 9. It consists of three parts: area, group, and serial numbers.',
    },
    {
      id: 3,
      name: 'CREDITCARDNUMBER',
      color: 'red',
      amount: '13,272',
      checked: true,
      description:
        'A US credit card number is a 16-digit number typically formatted as XXXX XXXX XXXX XXXX, where "X" represents a digit from 0 to 9. It includes the Issuer Identifier, account number, and a check digit.',
    },
    {
      id: 4,
      name: 'LOCATION',
      color: 'green',
      amount: '2,576,904',
      checked: true,
      description: `A US address format includes the recipient's name, street address (number and name), city, state abbreviation, and ZIP code, for example: John Doe 123 Main St Springfield, IL 62701`,
    },
    {
      id: 5,
      name: 'NAME',
      color: 'purple',
      amount: '1,758,131',
      checked: true,
      description: `An English name format typically consists of a first name, middle name(s), and last name (surname), for example: John Michael Smith. Titles and suffixes, like Mr. or Jr., may also be included.`,
    },
  ];

  return (
    <Card
      style={{
        animation: 'fade-in 0.5s',
        display: 'flex',
        flexDirection: 'row',
      }}
    >
      <TextContainer>
        <Header
          onClick={(e) => {
            onOpen(e);

            // TODO(Any): use update query text and uncomment below to record implicit-feedback
            // Capture the query text and complete the telemetry event for implicit feedback.
            const feedback = {
              reference_id: info.id,
              reference_rank: 0, // TODO: fill actual rank
              query_text: query || '',
              event_desc: 'open_reference_source',
            };

            console.log('feedback logged:', feedback);

            // Record the implicit feedback
            modelService
              .recordImplicitFeedback(feedback)
              .then((data) => {
                console.log('Implicit feedback recorded successfully:', data);
              })
              .catch((error) => {
                console.error('Error recording implicit feedback:', error);
                alert('Error recording implicit feedback:' + error);
              });
          }}
          target={'_blank'}
        >
          {info.sourceName}
          <Spacer $width="10px" />
          {isReadableSource(info.sourceName) && (
            <ReadSourceButton>
              Read source <StyledArrow />
            </ReadSourceButton>
          )}
        </Header>
        <Content>
          {piiMap ? (
            <div className="ner-block">
              {getTokensAndTags(info.content, piiMap).map((token_tag, sentenceIndex) => {
                const label = labels.find((label) => label.name === token_tag.tag);
                return (
                  <span
                    key={sentenceIndex}
                    // data-paragraph-index={paragraphIndex}
                    // data-sentence-index={sentenceIndex}
                    // onClick={() => {
                    //     if (label && label.checked) {
                    //         handleSpanClick(paragraphIndex, sentenceIndex);
                    //     }
                    // }}
                    style={{
                      color: label && label.checked ? label.color : 'inherit',
                      cursor: label && label.checked ? 'pointer' : 'auto',
                    }}
                  >
                    {label && label.checked ? `${token_tag.token} (${token_tag.tag})` : `${token_tag.token} `}
                  </span>
                );
              })}
            </div>
          ) : (
            <Content> {info.content} </Content>
          )}
        </Content>
      </TextContainer>
      <ButtonsContainer>
        <VoteButtonsContainer>
          <input type="checkbox" checked={checked} onChange={onCheck} />
          <Spacer $height="10px" />
          <UpvoteButton onClick={onUpvote} />
          <Spacer $height="10px" />
          <DownvoteButton onClick={onDownvote} />
        </VoteButtonsContainer>
        <Spacer $height={padding.card} />
        <CopyButton toCopy={info.content} referenceID={info.id} queryText={query} />
      </ButtonsContainer>
    </Card>
  );
}
