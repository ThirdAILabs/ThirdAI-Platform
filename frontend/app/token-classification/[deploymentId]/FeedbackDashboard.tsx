import React, { MouseEventHandler, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';

interface HighlightColor {
  text: string;
  tag: string;
}

interface HighlightProps {
  currentToken: Token;
  nextToken?: Token | null;
  tagColors: Record<string, HighlightColor>;
  onMouseOver: MouseEventHandler;
  onMouseDown: MouseEventHandler;
  selecting: boolean;
  selected: boolean;
}

const SELECTING_COLOR = '#EFEFEF';
const SELECTED_COLOR = '#DFDFDF';

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
        style={{
          backgroundColor:
            hover || selecting
              ? SELECTING_COLOR
              : selected
                ? SELECTED_COLOR
                : tagColors[currentToken.tag]?.text || 'transparent',
          padding: '2px',
          borderRadius: '2px',
          cursor: hover ? 'pointer' : 'default',
          userSelect: 'none',
        }}
        onMouseOver={(e) => {
          setHover(true);
          onMouseOver(e);
        }}
        onMouseLeave={(e) => {
          setHover(false);
        }}
        onMouseDown={onMouseDown}
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
      </span>
      <span
        style={{ cursor: hover ? 'pointer' : 'default', userSelect: 'none' }}
        onMouseOver={(e) => {
          setHover(true);
          onMouseOver(e);
        }}
        onMouseLeave={(e) => {
          setHover(false);
        }}
        onMouseDown={onMouseDown}
      >
        {' '}
      </span>
    </>
  );
}

interface Token {
  text: string;
  tag: string;
}

interface ColumnData {
  columnName: string;
  content: Token[];
}

type CachedTagEntry = Token[] | ColumnData;

interface CachedTags {
  [key: string]: CachedTagEntry;
}

interface HighlightColor {
  text: string;
  tag: string;
}

interface FeedbackDashboardProps {
  cachedTags: CachedTags;
  tagColors: Record<string, HighlightColor>;
  deleteFeedbackExample: (sentence: string) => void;
  submitFeedback: () => void;
}

const FeedbackDashboard: React.FC<FeedbackDashboardProps> = ({
  cachedTags,
  tagColors,
  deleteFeedbackExample,
  submitFeedback,
}) => {
  const renderFeedbackContent = (entry: CachedTagEntry) => {
    if (Array.isArray(entry)) {
      // Handle non-CSV/XLSX content
      return entry.map((token, index) => renderToken(token, `content-${index}`));
    } else if ('columnName' in entry && 'content' in entry) {
      // Handle CSV/XLSX content
      return (
        <>
          <strong>{entry.columnName}:</strong>{' '}
          {entry.content.map((token, index) => renderToken(token, `content-${index}`))}
        </>
      );
    }
    return null;
  };

  const renderToken = (token: Token, key: string | number) => {
    if (token.tag !== 'O') {
      return (
        <Highlight
          key={key}
          currentToken={token}
          nextToken={null}
          tagColors={tagColors}
          onMouseOver={() => {}}
          onMouseDown={() => {}}
          selecting={false}
          selected={false}
        />
      );
    } else {
      return <React.Fragment key={key}>{token.text} </React.Fragment>;
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">Feedback from this session</h3>
      {Object.entries(cachedTags).map(([sentence, tags], index) => (
        <div key={index} className="mb-4 flex items-start">
          <div style={{ flex: 1, lineHeight: 2 }}>{renderFeedbackContent(tags)}</div>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => deleteFeedbackExample(sentence)}
            style={{ marginLeft: '10px', padding: '0 10px', height: '24px', fontSize: '12px' }}
          >
            DELETE
          </Button>
        </div>
      ))}
      <Button
        size="sm"
        style={{ marginTop: '20px' }}
        onClick={submitFeedback}
        disabled={Object.keys(cachedTags).length === 0}
      >
        Submit Feedback
      </Button>
    </div>
  );
};

export default FeedbackDashboard;
