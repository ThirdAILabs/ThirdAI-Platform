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
        <div className="text-muted-foreground text-sm">
          Token Classification
        </div>
        <div className="font-bold text-xl truncate" title={workflowName}>
          {workflowName}
        </div>
      </div>
    </header>

    <main className="pt-24"> {/* Adjust padding-top to account for fixed header */}
      <Tabs defaultValue="interact" className="w-full">
        <div className="flex justify-center mb-4">
          <TabsList style={{ backgroundColor: 'rgba(0,0,0,0.05)' }}>
            <TabsTrigger value="interact">Interact</TabsTrigger>
            <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="interact">
          <Interact />
        </TabsContent>
        <TabsContent value="dashboard">
          <Dashboard />
        </TabsContent>
      </Tabs>
    </main>
  </div>
  );
}
