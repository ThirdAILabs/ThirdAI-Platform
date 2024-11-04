'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchFeedback } from '@/lib/backend';
import { useState, useEffect } from 'react';
import { Typography, IconButton } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

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

// RecentFeedbacks component updates:
interface RecentFeedbacksProps {
  username: string;
  modelName: string;
}

export default function RecentFeedbacks({ username, modelName }: RecentFeedbacksProps) {
  const [recentUpvotes, setRecentUpvotes] = useState([]);
  const [recentAssociations, setRecentAssociations] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  // Initial load when component mounts
  useEffect(() => {
    getFeedbackData();
  }, [username, modelName]);

  const getFeedbackData = async () => {
    if (!username || !modelName) return;

    setIsLoading(true);
    try {
      const data = await fetchFeedback(username, modelName);
      console.log('recent feedback data -> ', data);
      setRecentUpvotes(data?.upvote);
      setRecentAssociations(data?.associate);
    } catch (error) {
      console.error('Error fetching feedback:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        padding: '0 2rem',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
        <IconButton
          onClick={getFeedbackData}
          disabled={isLoading}
          color="primary"
          size="large"
          className={isLoading ? 'animate-spin' : ''}
        >
          <RefreshIcon />
        </IconButton>
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          width: '100%',
        }}
      >
        <Card style={{ width: '48%', minHeight: '45rem' }} className="pb-2">
          <CardHeader className="bg-blue-900 text-white mb-3">
            <CardTitle>Recent Upvotes</CardTitle>
            <CardDescription className="text-white">
              The latest user-provided upvotes
            </CardDescription>
          </CardHeader>
          <CardContent style={{ overflowY: 'auto', maxHeight: '45rem' }}>
            {recentUpvotes ? (
              recentUpvotes.map(({ timestamp, query, reference_id, reference_text }, idx) => (
                <TextPairs
                  key={idx}
                  timestamp={timestamp}
                  label1="Query"
                  label2="Upvote"
                  text1={query}
                  text2={reference_text}
                />
              ))
            ) : (
              <div className="flex flex-col justify-center items-center h-full mt-20">
                <img src="/no-Data-Png.png" alt="No Data Available" className="mb-4" />
                <span className="font-mono italic">Oops! No upvotes data available.</span>
              </div>
            )}
          </CardContent>
        </Card>
        <Card style={{ width: '48%', minHeight: '45rem' }}>
          <CardHeader className="bg-blue-900 text-white mb-3">
            <CardTitle>Recent Associations</CardTitle>
            <CardDescription className="text-white">
              The latest user-provided associations
            </CardDescription>
          </CardHeader>
          <CardContent style={{ overflowY: 'auto', maxHeight: '45rem' }}>
            {recentAssociations ? (
              recentAssociations.map(({ timestamp, source, target }, idx) => (
                <TextPairs
                  key={idx}
                  timestamp={timestamp}
                  label1="Source"
                  label2="Target"
                  text1={source}
                  text2={target}
                />
              ))
            ) : (
              <div className="flex flex-col justify-center items-center h-full mt-20">
                <img src="/no-Data-Png.png" alt="No Data Available" className="mb-4" />
                <span className="font-mono italic">Oops! No Associations data available.</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
