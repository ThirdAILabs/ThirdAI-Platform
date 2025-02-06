import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@mui/material';
import { Trash2 } from 'lucide-react';

interface Selection {
  start: number;
  end: number;
  xpath: string;
  tag: string;
  value: string;
}

interface FeedbackDashboardProps {
  selections: Selection[];
  xmlString: string; // Include the XML string for feedback submission
  onDeleteSelection?: (index: number) => void;
}

interface Feedback {
  text: string;
  label: string;
}

function FeedbackItem({
  feedback,
  index,
  onDeleteSelection,
}: {
  feedback: Feedback;
  index: number;
  onDeleteSelection?: (index: number) => void;
}) {
  return (
    <div className="feedback-item bg-white p-4 rounded-lg shadow-md mb-4">
      <div className="flex justify-between items-center gap-1">
        <div className="feedback-item-text text-gray-800">
          {feedback.text}
          <span className="feedback-item-label bg-green-400 text-white px-2 py-1 rounded-lg ml-1 text-sm">
            {feedback.label}
          </span>
        </div>
        <Button
          variant="contained"
          color="error"
          className="hover:bg-red-500 hover:text-white"
          onClick={() => onDeleteSelection?.(index)}
        >
          {<Trash2 className="h-6 w-5"></Trash2>}
        </Button>
      </div>
    </div>
  );
}

export function FeedbackDashboard({
  selections,
  xmlString,
  onDeleteSelection,
}: FeedbackDashboardProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submitFeedbacks = async () => {
    try {
      const url = new URL(window.location.href);
      const deploymentURL = url?.origin + '/' + url?.pathname?.split('/')?.slice(-1);
      console.log('deploymentURL ', deploymentURL);
      setIsSubmitting(true);

      // Transform selections into XMLUserFeedback structure
      const feedbackData = {
        xml_string: xmlString,
        feedbacks: selections.map((selection) => ({
          location: { xpath: selection.xpath, attribute: null },
          charspan: { start: selection.start, end: selection.end },
          label: selection.tag,
        })),
      };
      const accessToken = localStorage.getItem('accessToken');
      console.log('feedback data: ', feedbackData);
      // Call backend API
      const response = await fetch(`${deploymentURL}/insert_sample`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`, // Add this if required
        },
        body: JSON.stringify({ tokens: ['ram', 'shyam'], tags: ['name', 'name'] }), //this is just for checking purpose.
        // body: JSON.stringify(feedbackData), //It will work after the merge of "xml-feedback-support" this branch.
      });

      if (response.ok) {
        alert('Feedback submitted successfully!');
      } else {
        const error = await response.json();
        console.error('Submission error:', error);
        alert('Error submitting feedback. Please try again.');
      }
    } catch (error) {
      console.error('Network error:', error);
      alert('An error occurred while submitting feedback. Please check your connection.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-4xl mx-auto" style={{ overflowY: 'auto' }}>
      <CardHeader>
        <CardTitle>Feedback from this session</CardTitle>
      </CardHeader>
      <CardContent>
        {selections.map((selection, index) => (
          <FeedbackItem
            key={index}
            feedback={{
              text: selection.value,
              label: selection.tag,
            }}
            index={index}
            onDeleteSelection={onDeleteSelection}
          />
        ))}
        <Button
          variant="contained"
          style={{ width: '100%', marginTop: '20px' }}
          onClick={submitFeedbacks}
          disabled={isSubmitting || selections.length === 0}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
        </Button>
      </CardContent>
    </Card>
  );
}

export default FeedbackDashboard;
