import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ModelsTable } from './models-table';
import CreateModelButton from '@/components/ui/create-model-button';
import ImportModelButton from '@/components/ui/import-model-button';

export default async function ModelsPage({
  searchParams
}: {
  searchParams: { q: string; offset: string };
}) {
  const search = searchParams.q ?? '';
  const offset = searchParams.offset ?? 5;

  return (
    <Tabs defaultValue="all">
      <div className="flex items-center">
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="active">Active</TabsTrigger>
          <TabsTrigger value="draft">Draft</TabsTrigger>
          <TabsTrigger value="archived" className="hidden sm:flex">
            Archived
          </TabsTrigger>
        </TabsList>
        <div className="ml-auto flex items-center gap-2">
          <ImportModelButton />
          <CreateModelButton />
        </div>
      </div>
      <TabsContent value="all">
        <ModelsTable
          searchStr={search}
          offset={Number(offset) ?? 0}
        />
      </TabsContent>
    </Tabs>
  );
}
