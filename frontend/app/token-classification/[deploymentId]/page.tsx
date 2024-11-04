'use client';

import { useEffect, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import * as _ from 'lodash';
import { useTokenClassificationEndpoints } from '@/lib/backend';
import Interact from './interact';
import Dashboard from './dashboard';

export default function Page() {
  const { workflowName } = useTokenClassificationEndpoints();

  return (
    <div className="bg-muted min-h-screen">
      <header className="w-full p-4 bg-muted">
        <div className="max-w-7xl mx-auto">
          <div className="text-muted-foreground text-sm">Token Classification</div>
          <div className="font-bold text-xl truncate" title={workflowName}>
            {workflowName}
          </div>
        </div>
      </header>

      <main className="pt-24">
        <Interact />
      </main>
    </div>
  );
}
