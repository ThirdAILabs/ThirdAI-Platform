'use client';

import Link from 'next/link';
import { PlusCircle } from 'lucide-react';
import { Button } from '@mui/material';

const CreateModelButton = () => {
  return (
    <Link href="/createmodel">
      <Button variant="contained">
        <PlusCircle className="h-3.5 w-3.5" />
        <span className="sr-only sm:not-sr-only sm:whitespace-nowrap">Create App</span>
      </Button>
    </Link>
  );
};

export default CreateModelButton;
