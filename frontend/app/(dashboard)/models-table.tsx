'use client';

import { useEffect, useState } from 'react';
import {
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  Table
} from '@/components/ui/table';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { Model } from './model';
import { SelectModel } from '@/lib/db';
import { useRouter } from 'next/navigation';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { fetchPublicModels, fetchPrivateModels, fetchPendingModels } from "@/lib/backend"

export function ModelsTable() {
  
  // Hardcode the model display
  const offset = 5
  const totalModels = 4
  let modelsPerPage = 5;

  let router = useRouter();

  function prevPage() {
    router.back();
  }

  function nextPage() {
    router.push(`/?offset=${offset}`, { scroll: false });
  }

  const [privateModels, setPrivateModels] = useState<SelectModel[]>([])
  const [pendingModels, setPendingModels] = useState<SelectModel[]>([]);

  useEffect(() => {
    async function getModels() {
        try {
          let response = await fetchPublicModels('');
          const publicModels = response.data;
          console.log('publicModels', publicModels)

          response = await fetchPrivateModels('');
          const privateModels: SelectModel[] = response.data;
          console.log('privateModels', privateModels)

          // const mappedModels = privateModels.map(mapPrivateModelToSelectModel);
          // console.log('mappedModels', mappedModels)
          setPrivateModels(privateModels)

          response = await fetchPendingModels();
          const pendingModels = response.data; // Extract the data field
          console.log('pendingModels', pendingModels)

          // const mappedPendingModels = pendingModels.map(mapPendingModelToSelectModel);
          // console.log('mappedPendingModels', mappedPendingModels);
          // setPendingModels(mappedPendingModels);

        } catch (err) {
          if (err instanceof Error) {
              console.log(err.message);
          } else {
              console.log('An unknown error occurred');
          }
      }
    }

    getModels();
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Models</CardTitle>
        <CardDescription>
          Manage your models and view their performance.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="hidden w-[100px] sm:table-cell">
                <span className="sr-only">Image</span>
              </TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="hidden md:table-cell">Type</TableHead>
              <TableHead className="hidden md:table-cell">Published at</TableHead>
              <TableHead className="hidden md:table-cell">Description</TableHead>
              <TableHead className="hidden md:table-cell">Endpoint</TableHead>
              <TableHead className="hidden md:table-cell">Deploy</TableHead>
              <TableHead>
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {privateModels.map((model, index) => (
                <Model key={index} model={model} />
            ))}

            {pendingModels.map((model) => (
                <Model key={model.id} model={model} />
            ))}
          </TableBody>
        </Table>
      </CardContent>
      <CardFooter>
        <form className="flex items-center w-full justify-between">
          <div className="text-xs text-muted-foreground">
            Showing{' '}
            <strong>
              {Math.min(offset - modelsPerPage, totalModels) + 1}-{offset}
            </strong>{' '}
            of <strong>{totalModels}</strong> models
          </div>
          <div className="flex">
            <Button
              formAction={prevPage}
              variant="ghost"
              size="sm"
              type="submit"
              disabled={offset === modelsPerPage}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              Prev
            </Button>
            <Button
              formAction={nextPage}
              variant="ghost"
              size="sm"
              type="submit"
              // disabled={offset + modelsPerPage > totalModels}
            >
              Next
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </form>
      </CardFooter>
    </Card>
  );
}
