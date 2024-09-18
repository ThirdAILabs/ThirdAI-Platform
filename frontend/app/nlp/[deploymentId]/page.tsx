'use client';

import { useParams } from 'next/navigation';
import { Container, TextField, Button, Box } from '@mui/material';
import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import * as _ from 'lodash';

interface NLPResult {
  source: string[];
  predicted_tags: string[];
}

interface Token {
  text: string;
  tag: string;
}

interface HighlightColor {
  text: string;
  tag: string;
}

interface HighlightProps {
  currentToken: Token;
  nextToken?: Token | null;
  tagColors: Record<string, HighlightColor>;
}

function Highlight({ currentToken, nextToken, tagColors }: HighlightProps) {
  return (
    <>
      <span
        style={{
          backgroundColor: tagColors[currentToken.tag]?.text || 'transparent',
          padding: '2px',
          borderRadius: '2px',
        }}
      >
        {currentToken.text}
        {tagColors[currentToken.tag] && nextToken?.tag !== currentToken.tag && (
          <span
            style={{
              backgroundColor: tagColors[currentToken.tag].tag,
              color: 'white',
              fontSize: '11px',
              fontWeight: 'bold',
              borderRadius: '2px',
              marginLeft: '4px',
              padding: '5px 3px 1px 3px',
              marginBottom: '1px',
            }}
          >
            {currentToken.tag}
          </span>
        )}
      </span>{' '}
    </>
  );
}

function generateColors(N: number) {
  const pastels = ['#E5A49C', '#F6C886', '#FBE7AA', '#99E3B5', '#A6E6E7', '#A5A1E1', '#D8A4E2'];
  const darkers = ['#D34F3E', '#F09336', '#F7CF5F', '#5CC96E', '#65CFD0', '#597CE2', '#B64DC8'];
  const colors = [];

  for (let i = 0; i < N; i++) {
    colors.push({
      pastelColor: pastels[i % pastels.length],
      darkerColor: darkers[i % darkers.length],
    });
  }

  return colors;
}

export default function Page() {
  const { deploymentId } = useParams();

  const infer = async (query: string): Promise<NLPResult> => {
    // TODO: Call endpoint
    return {
      source: [
        'Peter',
        'is',
        'a',
        'frontend',
        'engineer',
        'from',
        'Houston.',
        '1111',
        '2222',
        '3333',
        '5555.',
        'His',
        'SSN',
        '123-12-1234.',
        'Call',
        'at',
        '123-123-1234',
      ],
      predicted_tags: [
        'NAME',
        'O',
        'O',
        'O',
        'O',
        'O',
        'LOCATION',
        'CREDITCARDNUMBER',
        'CREDITCARDNUMBER',
        'CREDITCARDNUMBER',
        'CREDITCARDNUMBER',
        'O',
        'O',
        'SSN',
        'O',
        'O',
        'PHONENUMBER',
      ],
    };
  };

  const [inputText, setInputText] = useState<string>('');
  const [annotations, setAnnotations] = useState<Token[]>([]);
  const [tagColors, setTagColors] = useState<Record<string, HighlightColor>>({});

  useEffect(() => {
    // TODO: Get list of tags from backend
    const tags = ['NAME', 'CREDITCARDNUMBER', 'SSN', 'PHONENUMBER', 'LOCATION'];
    const colors = generateColors(tags.length);
    setTagColors(
      Object.fromEntries(
        tags.map((tag, index) => [
          tag,
          { text: colors[index].pastelColor, tag: colors[index].darkerColor },
        ])
      )
    );
  }, []);

  const handleInputChange = (event: any) => {
    setInputText(event.target.value);
  };

  const handleRun = () => {
    infer(inputText).then((result) => {
      setAnnotations(
        _.zip(result.source, result.predicted_tags).map(([text, tag]) => ({
          text: text as string,
          tag: tag as string,
        }))
      );
    });
  };

  return (
    <Container
      style={{
        textAlign: 'center',
        paddingTop: '20vh',
        width: '70%',
        minWidth: '400px',
        maxWidth: '800px',
      }}
    >
      <Box display="flex" justifyContent="center" alignItems="center" width="100%">
        <TextField
          variant="outlined"
          value={inputText}
          onChange={handleInputChange}
          style={{ width: '100%' }}
          placeholder="Enter your text"
          InputProps={{ style: { height: '3rem' } }} // Adjust the height as needed
        />
        <Button
          variant="contained"
          color="primary"
          onClick={handleRun}
          style={{
            height: '3rem',
            marginLeft: '1rem',
            backgroundColor: 'black',
          }}
        >
          Run
        </Button>
      </Box>
      {annotations.length > 0 && (
        <Box mt={4}>
          <Card className="p-7 text-start" style={{ lineHeight: 2 }}>
            {annotations.map((token, index) => {
              const nextToken = index === annotations.length - 1 ? null : annotations[index + 1];
              return (
                <Highlight
                  key={index}
                  currentToken={token}
                  nextToken={nextToken}
                  tagColors={tagColors}
                />
              );
            })}
          </Card>
        </Box>
      )}
    </Container>
  );
}
