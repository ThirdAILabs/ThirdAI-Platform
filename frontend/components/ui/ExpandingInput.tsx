import React, { useState, useRef, useEffect, ChangeEvent, KeyboardEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Paperclip, Send } from 'lucide-react';

interface EnhancedInputProps {
  onSubmit: (text: string) => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
}

const ExpandingInput: React.FC<EnhancedInputProps> = ({
  onSubmit,
  onFileChange,
  onInputChange,
}) => {
  const [inputText, setInputText] = useState<string>('');
  const [showTooltip, setShowTooltip] = useState<boolean>(false);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    adjustHeight();
  }, [inputText]);

  const adjustHeight = () => {
    const textarea = textAreaRef.current;
    if (textarea) {
      textarea.style.height = '3rem';
      const maxHeight = 11 * parseFloat(getComputedStyle(textarea).lineHeight);
      const newHeight = Math.min(textarea.scrollHeight, maxHeight);
      textarea.style.height = `${newHeight}px`;
    }
  };

  const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    // Invoke onInputChange callback for the text area changes
    onInputChange(e as unknown as ChangeEvent<HTMLInputElement>); // Casting as a workaround
  };

  const handleSubmit = () => {
    if (inputText.trim()) {
      onSubmit(inputText);
      setInputText('');
      if (textAreaRef.current) {
        textAreaRef.current.style.height = '3rem';
      }
    }
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-full">
      <div className="flex items-end gap-2">
        <div className="relative">
          <Button
            variant="ghost"
            size="sm"
            className="h-12 w-12"
            onClick={handleFileClick}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <Paperclip className="h-5 w-5" />
          </Button>
          {showTooltip && (
            <div className="absolute bottom-full left-0 mb-2 px-3 py-2 text-sm bg-gray-900 text-white rounded-md whitespace-nowrap z-50">
              Supported file types: .txt, .pdf, .docx, .csv, .xls, .xlsx (Max size: 1MB)
              <div className="absolute top-full left-6 border-8 border-transparent border-t-gray-900" />
            </div>
          )}
        </div>

        <textarea
          ref={textAreaRef}
          className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
          style={{
            minHeight: '3rem',
            maxHeight: '11em',
            overflowY: 'auto',
          }}
          value={inputText}
          onChange={handleTextChange}
          placeholder="Enter your text..."
          onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />

        {inputText && (
          <Button size="sm" className="h-12 w-12" onClick={handleSubmit}>
            <Send className="h-5 w-5" />
          </Button>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.pdf,.docx,.csv,.xls,.xlsx"
          onChange={onFileChange}
          className="hidden"
        />
      </div>
    </div>
  );
};

export default ExpandingInput;
