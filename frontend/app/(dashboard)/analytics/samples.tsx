'use client';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';

interface TextPairsProps {
  timestamp: string;
  label1: string;
  label2: string;
  text1: string;
  text2: string;
}

function TextPairs({
  timestamp,
  label1,
  label2,
  text1,
  text2
}: TextPairsProps) {
  return (
    <div
      className="text-md"
      style={{ display: 'flex', flexDirection: 'column', marginBottom: '10px' }}
    >
      <CardDescription>{timestamp}</CardDescription>
      <div
        className="text-md"
        style={{ display: 'flex', flexDirection: 'row' }}
      >
        <span style={{ fontWeight: 'bold', marginRight: '5px' }}>
          {label1}:
        </span>
        <span style={{}}>{text1}</span>
      </div>
      <div
        className="text-md"
        style={{ display: 'flex', flexDirection: 'row' }}
      >
        <span style={{ fontWeight: 'bold', marginRight: '5px' }}>
          {label2}:
        </span>
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

function Reformulation({
  timestamp,
  original,
  reformulations
}: ReformulationProps) {
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

export default function RecentSamples() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'space-between',
        width: '100%'
      }}
    >
      <Card style={{ width: '32.5%' }}>
        <CardHeader>
          <CardTitle>Recent Upvotes</CardTitle>
          <CardDescription>The latest user-provided upvotes</CardDescription>
        </CardHeader>
        <CardContent>
          {[
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              query: 'A nice pair of shoes',
              upvote: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              query: 'A nice pair of shoes',
              upvote: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              query: 'A nice pair of shoes',
              upvote: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              query: 'A nice pair of shoes',
              upvote: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              query: 'A nice pair of shoes',
              upvote: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              query: 'A nice pair of shoes',
              upvote: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              query: 'A nice pair of shoes',
              upvote: "New Balance Men's 574 Core Sneakers"
            }
          ].map(({ timestamp, query, upvote }, idx) => (
            <TextPairs
              key={idx}
              timestamp={timestamp}
              label1="Query"
              label2="Upvote"
              text1={query}
              text2={upvote}
            />
          ))}
        </CardContent>
      </Card>
      <Card style={{ width: '32.5%' }}>
        <CardHeader>
          <CardTitle>Recent Associations</CardTitle>
          <CardDescription>
            The latest user-provided associations
          </CardDescription>
        </CardHeader>
        <CardContent>
          {[
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              source: 'A nice pair of shoes',
              target: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              source: 'A nice pair of shoes',
              target: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              source: 'A nice pair of shoes',
              target: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              source: 'A nice pair of shoes',
              target: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              source: 'A nice pair of shoes',
              target: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              source: 'A nice pair of shoes',
              target: "New Balance Men's 574 Core Sneakers"
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              source: 'A nice pair of shoes',
              target: "New Balance Men's 574 Core Sneakers"
            }
          ].map(({ timestamp, source, target }, idx) => (
            <TextPairs
              key={idx}
              timestamp={timestamp}
              label1="Source"
              label2="Target"
              text1={source}
              text2={target}
            />
          ))}
        </CardContent>
      </Card>
      <Card style={{ width: '32.5%' }}>
        <CardHeader>
          <CardTitle>Recent Query Reformulations</CardTitle>
          <CardDescription>
            The latest queries that required reformulation
          </CardDescription>
        </CardHeader>
        <CardContent>
          {[
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              original: 'A nice pair of shoes',
              reformulations: [
                'Shoes that are trendy',
                'Shoes that people like',
                'Great shoes for running',
                'Shoes that look good'
              ]
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              original: 'A nice pair of shoes',
              reformulations: [
                'Shoes that are trendy',
                'Shoes that people like',
                'Great shoes for running',
                'Shoes that look good'
              ]
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              original: 'A nice pair of shoes',
              reformulations: [
                'Shoes that are trendy',
                'Shoes that people like',
                'Great shoes for running',
                'Shoes that look good'
              ]
            },
            {
              timestamp: 'Aug 9, 2024 at 12:31 AM',
              original: 'A nice pair of shoes',
              reformulations: [
                'Shoes that are trendy',
                'Shoes that people like',
                'Great shoes for running',
                'Shoes that look good'
              ]
            }
          ].map(({ timestamp, original, reformulations }, idx) => (
            <Reformulation
              key={idx}
              timestamp={timestamp}
              original={original}
              reformulations={reformulations}
            />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
