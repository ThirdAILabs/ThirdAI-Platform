import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ModelsTable } from './models-table';
import CreateModelButton from '@/components/ui/create-model-button';
import ImportModelButton from '@/components/ui/import-model-button';

export default async function ModelsPage({
  searchParams,
}: {
  searchParams: { q: string; offset: string };
}) {
  const search = searchParams.q ?? '';
  const offset = parseInt(searchParams.offset, 10) || 0;

  return (
    <Tabs defaultValue="all">
      <div className="flex items-center">
        <div className="ml-auto flex items-center gap-2">
          <ImportModelButton />
          <CreateModelButton />
        </div>
      </div>
      <TabsContent value="all">
        <ModelsTable searchStr={search} offset={Number(offset) ?? 0} />
      </TabsContent>
    </Tabs>
  );
}
