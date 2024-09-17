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
    <div
      className="bg-muted"
      style={{ width: '100%', display: 'flex', justifyContent: 'center', height: '100vh' }}
    >
      <Tabs defaultValue="interact" style={{ width: '100%' }}>
        <div style={{ position: 'fixed', top: '20px', left: '20px' }}>
          <div className="text-muted-foreground" style={{ fontSize: '16px' }}>
            Token Classification
          </div>
          <div style={{ fontWeight: 'bold', fontSize: '24px' }}>{workflowName}</div>
        </div>
        <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'center' }}>
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
    </div>
  );
}
