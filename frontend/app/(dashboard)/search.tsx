'use client';

import { useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { TextField, InputAdornment } from '@mui/material';
import { Spinner } from '@/components/icons';
import SearchIcon from '@mui/icons-material/Search';
export function SearchInput() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function searchAction(formData: FormData) {
    let value = formData.get('q') as string;
    let params = new URLSearchParams({ q: value });
    startTransition(() => {
      router.replace(`/?${params.toString()}`);
    });
  }

  return (
    <form action={searchAction} className="relative ml-auto flex-1 md:grow-0">
      <TextField
        name="q"
        type="search"
        placeholder="Search..."
        className="w-80"
        InputProps={{
          startAdornment: (
            <InputAdornment position="start" style={{ backgroundColor: 'white' }}>
              <SearchIcon className="text-muted-foreground" />
            </InputAdornment>
          ),
          style: { backgroundColor: 'white' }, // Ensures the input field background is white
        }}
      />
      {isPending && <Spinner />}
    </form>
  );
}
