'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import Models from './models';
import Workflows from './workflows';
import Teams from './teams';
import Users from './users';
import OpenAIKey from './apiKey';
import { UserContext } from '../../user_wrapper';
import { usePathname, useSearchParams } from 'next/navigation';

function AccessContent() {
  const { user } = React.useContext(UserContext);
  const [activeTab, setActiveTab] = useState('models');
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    // Get the active tab from the URL search params on initial load
    const tab = searchParams.get('tab');
    if (tab && ['models', 'workflows', 'teams', 'users', 'openai'].includes(tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    // Update the URL search params when changing tabs
    const newSearchParams = new URLSearchParams(searchParams.toString());
    newSearchParams.set('tab', value);
    window.history.pushState(null, '', `${pathname}?${newSearchParams.toString()}`);
  };

  // Determine the user role
  let userRole = '';
  let roleDescription = '';
  if (user?.global_admin) {
    userRole = 'Global Admin';
    roleDescription =
      'This role has read and write access to all members, models, and applications.';
  } else if (user?.teams.some((team) => team.role === 'team_admin')) {
    userRole = 'Team Admin';
    roleDescription =
      'This role has read and write access to all team members, models, and applications in the team.';
  } else {
    userRole = 'User';
    roleDescription = 'This role has limited access based on specific team permissions.';
  }

  return (
    <div className="container mx-auto p-6 bg-gray-50 min-h-screen">
      <Card className="shadow-lg max-w-4xl mx-auto">
        <CardHeader className="bg-blue-500 text-white p-6 rounded-t-lg">
          <CardTitle className="text-2xl font-bold">Manage Access</CardTitle>
          <CardDescription className="text-white">
            View all personnel and their access.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6 bg-white rounded-b-lg">
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-800">{userRole}</h2>
            <p className="text-gray-600">{roleDescription}</p>
          </div>

          <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="models" className="flex-1">
                Models
              </TabsTrigger>
              <TabsTrigger value="workflows" className="flex-1">
                Workflows
              </TabsTrigger>
              {user?.teams.length && (
                <TabsTrigger value="teams" className="flex-1">
                  Teams
                </TabsTrigger>
              )}

              <TabsTrigger value="users" className="flex-1">
                Users
              </TabsTrigger>
              {user?.global_admin && (
                <TabsTrigger value="openai" className="flex-1">
                  API Key
                </TabsTrigger>
              )}
            </TabsList>
            <div className="mt-6 w-full">
              <TabsContent value="models" className="w-full">
                <Models />
              </TabsContent>
              <TabsContent value="workflows" className="w-full">
                <Workflows />
              </TabsContent>
              <TabsContent value="teams" className="w-full">
                <Teams />
              </TabsContent>
              <TabsContent value="users" className="w-full">
                <Users />
              </TabsContent>
              <TabsContent value="openai" className="w-full">
                <OpenAIKey />
              </TabsContent>
            </div>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

export default function AccessPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <AccessContent />
    </Suspense>
  );
}
