"use client"

import { File, PlusCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useRef } from 'react';

const ImportModelButton = () => {

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      console.log('Selected file:', file);
      // Add your file handling logic here
    }
  };

  return (
    <>
        <Button size="sm" variant="outline" className="h-8 gap-1" onClick={()=>{
            if (fileInputRef.current) {
              fileInputRef.current.click();
            }
          }}>
            <File className="h-3.5 w-3.5" />
            <span className="sr-only sm:not-sr-only sm:whitespace-nowrap">
              Import App
            </span>
        </Button>
        <input
            type="file"
            ref={fileInputRef}
            accept=".ndb"
            style={{ display: 'none' }}
            onChange={handleFileChange}
        />
    </>
  );
};

export default ImportModelButton;
