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
import { WorkFlow } from './workflow';
import { SelectModel } from '@/lib/db';
import { useRouter } from 'next/navigation';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { fetchPublicModels, fetchPrivateModels, fetchPendingModels, fetchWorkflows, Workflow } from "@/lib/backend"

export function ModelsTable({
  searchStr,
  offset,
}: {
  searchStr: string;
  offset: number;
}) {
  
  // Hardcode the model display
  let modelsPerPage = 5;

  const [currentPage, setCurrentPage] = useState(Math.ceil(offset / modelsPerPage) + 1);

  let router = useRouter();

  function prevPage() {
    if (offset >= modelsPerPage) {
      const newOffset = offset - modelsPerPage;
      router.push(`/?q=${searchStr}&offset=${newOffset}`, { scroll: false });
    }
  }

  function nextPage() {
    if (offset + modelsPerPage < totalWorkflows) {
      const newOffset = offset + modelsPerPage;
      router.push(`/?q=${searchStr}&offset=${newOffset}`, { scroll: false });
    }
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

          setPrivateModels(privateModels)

          response = await fetchPendingModels();
          const pendingModels: SelectModel[] = response.data; // Extract the data field
          console.log('pendingModels', pendingModels)

          setPendingModels(pendingModels)

        } catch (err) {
          if (err instanceof Error) {
              console.log(err.message);
          } else {
              console.log('An unknown error occurred');
          }
      }
    }

    const intervalId = setInterval(getModels, 3000);

    // Cleanup function to clear the interval when the component unmounts
    return () => clearInterval(intervalId);
  }, []);

  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  useEffect(() => {
    async function getWorkflows() {
      try {
        const fetchedWorkflows = await fetchWorkflows();
        console.log('workflows', fetchedWorkflows);
        setWorkflows(fetchedWorkflows);
      } catch (err) {
        if (err instanceof Error) {
          console.log(err.message);
        } else {
          console.log('An unknown error occurred');
        }
      }
    }

    const intervalId = setInterval(getWorkflows, 3000);

    return () => clearInterval(intervalId);
  }, []);

  const totalWorkflows = workflows.length;

  // const displayedWorkflows = workflows.slice(offset, offset + modelsPerPage);
  const filteredWorkflows = workflows.filter(workflow =>
    workflow.name.toLowerCase().includes(searchStr.toLowerCase())
  );
  const displayedWorkflows = filteredWorkflows.slice(offset, offset + modelsPerPage);


  return (
    <Card>
      <CardHeader>
        <CardTitle>Apps</CardTitle>
        <CardDescription>
          Manage your Apps and view their performance.
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
              <TableHead className="hidden md:table-cell">Published on</TableHead>
              <TableHead className="hidden md:table-cell">Action</TableHead>
              <TableHead>
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* {privateModels.map((model, index) => (
                <Model key={index} model={model} />
            ))}

            {pendingModels.map((model, index) => (
                <Model key={index + 100} model={model} pending = {true} />
            ))}  */}

            {/* {workflows.map((workflow, index) => (
                <WorkFlow key={index + 200} workflow={workflow} />
            ))} */}
            {displayedWorkflows.map((workflow, index) => (
              <WorkFlow key={index + 200} workflow={workflow} />
            ))}
          </TableBody>
        </Table>
      </CardContent>
      <CardFooter>
        <form className="flex items-center w-full justify-between">
          <div className="text-xs text-muted-foreground">
            Showing{' '}
            <strong>
              {Math.min(offset + 1, totalWorkflows)}-{Math.min(offset + modelsPerPage, totalWorkflows)}
            </strong>{' '}
            of <strong>{totalWorkflows}</strong> workflows
          </div>
          <div className="flex">
            <Button
              onClick={prevPage}
              variant="ghost"
              size="sm"
              type="button"
              disabled={offset <= 0}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              Prev
            </Button>
            <Button
              onClick={nextPage}
              variant="ghost"
              size="sm"
              type="button"
              disabled={offset + modelsPerPage >= totalWorkflows}
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
