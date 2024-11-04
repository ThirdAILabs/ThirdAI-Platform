import React, { useCallback, useContext, useRef, useState } from 'react';
import { Button } from '@mui/material';
import { ModelServiceContext } from '../Context';
import { ModelService } from '../modelServices';
import TeachSVG from '../assets/icons/teach.svg';
import TeachPanel from './TeachPanel';
import useClickOutside from './hooks/useClickOutside';

const Teach = () => {
  const [showPanel, setShowPanel] = useState(false);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const modelService = useContext<ModelService | null>(ModelServiceContext);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleClickOutside = useCallback(() => {
    setShowPanel(false);
  }, []);

  useClickOutside(containerRef, handleClickOutside);

  const togglePanel = () => {
    setShowPanel((prev) => !prev);
  };

  return (
    <div className="relative" ref={containerRef}>
      <Button
        variant="contained"
        color="primary"
        style={{
          width: '48px',
          height: '48px',
          minWidth: 'unset',
          padding: '12px',
        }}
        onClick={togglePanel}
      >
        <TeachSVG
          style={{
            width: '24px',
            height: '24px',
            filter: 'brightness(0) invert(1)',
          }}
        />
      </Button>

      {showPanel && (
        <div className="absolute top-[-160px] right-full mr-2 w-[300px]">
          <TeachPanel
            question={question}
            answer={answer}
            canAddAnswer={true}
            setQuestion={setQuestion}
            setAnswer={setAnswer}
            onAddAnswer={(q, a) => modelService?.qna(q, a)}
            onAssociate={(q, a) => modelService?.associate(q, a)}
          />
        </div>
      )}
    </div>
  );
};

export default Teach;
