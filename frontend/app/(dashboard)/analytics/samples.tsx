'use client';
import React, { useState, useEffect, useRef, MouseEvent as ReactMouseEvent } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useLabels, useRecentSamples } from '@/lib/backend';
import { associations, reformulations, upvotes } from './mock_samples';
import useRollingSamples from './rolling';
import axios from 'axios';

const Separator: React.FC = () => <hr className="my-3 border-t border-gray-200" />;

interface TextPairsProps {
  timestamp: string;
  label1: string;
  label2: string;
  text1: string;
  text2: string;
}

function TextPairs({ timestamp, label1, label2, text1, text2 }: TextPairsProps) {
  return (
    <div
      className="text-md"
      style={{ display: 'flex', flexDirection: 'column', marginBottom: '10px' }}
    >
      <CardDescription>{timestamp}</CardDescription>
      <div className="text-md" style={{ display: 'flex', flexDirection: 'row' }}>
        <span style={{ fontWeight: 'bold', marginRight: '5px' }}>{label1}:</span>
        <span style={{}}>{text1}</span>
      </div>
      <div className="text-md" style={{ display: 'flex', flexDirection: 'row' }}>
        <span style={{ fontWeight: 'bold', marginRight: '5px' }}>{label2}:</span>
        <span>{text2}</span>
      </div>
    </div>
  );
}

interface ReformulationProps {
  timestamp: string;
  original: string;
  reformulations: string[];
}

function Reformulation({ timestamp, original, reformulations }: ReformulationProps) {
  return (
    <div
      className="text-md"
      style={{ display: 'flex', flexDirection: 'column', marginBottom: '10px' }}
    >
      <CardDescription>{timestamp}</CardDescription>
      <span className="text-md" style={{ fontWeight: 'bold' }}>
        {original}
      </span>
      {reformulations.map((r, i) => (
        <span key={i} className="text-md" style={{ marginLeft: '10px' }}>
          {r}
        </span>
      ))}
    </div>
  );
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
  onMouseOver: (e: ReactMouseEvent<HTMLSpanElement>) => void;
  onMouseDown: (e: ReactMouseEvent<HTMLSpanElement>) => void;
  selecting: boolean;
  selected: boolean;
}

function Highlight({
  currentToken,
  nextToken,
  tagColors,
  onMouseOver,
  onMouseDown,
  selecting,
  selected,
}: HighlightProps) {
  const [hover, setHover] = useState<boolean>(false);

  return (
    <>
      <span
        className={`
          inline-block px-1 py-0.5 rounded transition-colors duration-200 ease-in-out
          ${hover || selecting ? 'bg-gray-200' : selected ? 'bg-gray-300' : ''}
        `}
        style={{
          backgroundColor: tagColors[currentToken.tag]?.text || 'transparent',
          cursor: hover ? 'pointer' : 'default',
          userSelect: 'none',
        }}
        onMouseOver={(e) => {
          setHover(true);
          onMouseOver(e);
        }}
        onMouseLeave={() => setHover(false)}
        onMouseDown={onMouseDown}
      >
        {currentToken.text}
        {tagColors[currentToken.tag] && nextToken?.tag !== currentToken.tag && (
          <span
            className="text-xs font-bold text-white rounded px-1 py-0.5 ml-1 align-text-top"
            style={{ backgroundColor: tagColors[currentToken.tag].tag }}
          >
            {currentToken.tag}
          </span>
        )}
      </span>
      <span className="mr-1" />
    </>
  );
}

interface HighlightedSampleProps {
  tokens: string[];
  tags: string[];
  tagColors: Record<string, HighlightColor>;
}

function HighlightedSample({ tokens, tags, tagColors }: HighlightedSampleProps) {
  return (
    <div className="mb-4 leading-relaxed">
      {tokens.map((token, index) => (
        <Highlight
          key={index}
          currentToken={{ text: token, tag: tags[index] }}
          nextToken={
            index < tokens.length - 1 ? { text: tokens[index + 1], tag: tags[index + 1] } : null
          }
          tagColors={tagColors}
          onMouseOver={() => {}}
          onMouseDown={() => {}}
          selecting={false}
          selected={false}
        />
      ))}
    </div>
  );
}

interface Upvote {
  query: string;
  upvote: string;
  timestamp: string;
}

interface Association {
  source: string;
  target: string;
  timestamp: string;
}

interface Reformulation {
  original: string;
  reformulations: string[];
  timestamp: string;
}

interface RecentSamplesProps {
  deploymentUrl: string;
}

export default function RecentSamples({ deploymentUrl }: RecentSamplesProps) {
  const { recentLabels, error: labelError } = useLabels({ deploymentUrl });
  const { recentSamples, error: sampleError } = useRecentSamples({ deploymentUrl });

  const recentUpvotes = useRollingSamples(upvotes, 5, 2, 0.2, 2);
  const recentAssociations = useRollingSamples(associations, 5, 2, 0.1, 3);
  const recentReformulations = useRollingSamples(reformulations, 3, 1, 0.4, 2);

  const predefinedColors: HighlightColor[] = [
    { text: '#FEE2E2', tag: '#EF4444' }, // Red
    { text: '#FEF3C7', tag: '#F59E0B' }, // Amber
    { text: '#D1FAE5', tag: '#10B981' }, // Emerald
    { text: '#DBEAFE', tag: '#3B82F6' }, // Blue
    { text: '#E0E7FF', tag: '#6366F1' }, // Indigo
    { text: '#EDE9FE', tag: '#8B5CF6' }, // Violet
    { text: '#FCE7F3', tag: '#EC4899' }, // Pink
  ];

  const [tagColors, setTagColors] = useState<Record<string, HighlightColor>>({});
  const colorAssignmentsRef = useRef<Record<string, HighlightColor>>({});

  useEffect(() => {
    const updateTagColors = () => {
      const allTags = recentSamples.flatMap((sample) => sample.tags);
      const uniqueTags = Array.from(new Set(allTags)).filter((tag) => tag !== 'O');
      const newColors: Record<string, HighlightColor> = {};

      uniqueTags.forEach((tag, index) => {
        if (colorAssignmentsRef.current[tag]) {
          newColors[tag] = colorAssignmentsRef.current[tag];
        } else if (index < predefinedColors.length) {
          newColors[tag] = predefinedColors[index];
        } else {
          const hue = (index * 137.508) % 360;
          newColors[tag] = {
            text: `hsl(${hue}, 70%, 90%)`,
            tag: `hsl(${hue}, 70%, 40%)`,
          };
        }
        colorAssignmentsRef.current[tag] = newColors[tag];
      });

      setTagColors(newColors);
    };

    updateTagColors();
  }, [recentSamples]);

  // Create a set of unique labels and convert it back to an array
  const uniqueLabels = Array.from(new Set(recentLabels));

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
      <Card className="h-[calc(100vh-16rem)] overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl font-semibold">Recent Labels</CardTitle>
          <CardDescription>The latest added labels</CardDescription>
        </CardHeader>
        <CardContent className="overflow-y-auto h-[calc(100%-5rem)]">
          {labelError && (
            <div className="text-red-500">Error fetching labels: {labelError.message}</div>
          )}
          {uniqueLabels.map((label, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && <Separator />}
              <div className="mb-2 p-2 bg-gray-100 rounded-md">
                <span className="font-medium">{label}</span>
              </div>
            </React.Fragment>
          ))}
        </CardContent>
      </Card>
      <Card className="h-[calc(100vh-16rem)] overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl font-semibold">Recent Samples</CardTitle>
          <CardDescription>The latest inserted samples</CardDescription>
        </CardHeader>
        <CardContent className="overflow-y-auto h-[calc(100%-5rem)]">
          {sampleError && (
            <div className="text-red-500">Error fetching samples: {sampleError.message}</div>
          )}
          {recentSamples.map((sample, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && <Separator />}
              <HighlightedSample tokens={sample.tokens} tags={sample.tags} tagColors={tagColors} />
            </React.Fragment>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
