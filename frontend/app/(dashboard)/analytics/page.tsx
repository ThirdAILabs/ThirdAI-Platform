'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import RecentSamples from './samples';
import RecentFeedbacks from './recentFeedbacks';
import UpdateButton from './updateButton';
import UsageStats from './usageStats';
import { UsageDurationChart, UsageFrequencyChart, ReformulatedQueriesChart } from './charts';
import { useEffect, useState, Suspense } from 'react';
import Link from 'next/link';
import { Button } from '@mui/material';
import { useSearchParams } from 'next/navigation';
import { getWorkflowDetails, deploymentBaseUrl } from '@/lib/backend';
import _ from 'lodash';

function AnalyticsContent() {
  const [isClient, setIsClient] = useState(false);
  const searchParams = useSearchParams();
  const workflowid = searchParams.get('id');
  const [deploymentUrl, setDeploymentUrl] = useState<string | undefined>();
  const [modelName, setModelName] = useState<string>('');
  const [username, setUsername] = useState<string>('');
  const [workflowtype, setWorkflowType] = useState<string>('');

  useEffect(() => {
    setIsClient(true);

    const init = async () => {
      if (workflowid) {
        try {
          const workflowDetails = await getWorkflowDetails(workflowid);

          console.log('workflowDetails', workflowDetails);
          setWorkflowType(workflowDetails.data.type);
          console.log(`here is: ${deploymentBaseUrl}/${workflowDetails.data.model_id}`);
          setDeploymentUrl(`${deploymentBaseUrl}/${workflowDetails.data.model_id}`);
          setModelName(workflowDetails.data.model_name);
          setUsername(workflowDetails.data.username);
        } catch (err) {
          console.error('Error fetching workflow details:', err);
        }
      }
    };

    init();
  }, [workflowid]);

  if (!isClient) {
    return null; // Return null on the first render to avoid hydration mismatch
  }
  if (workflowtype == 'udt')
    return (
      <div className="container mx-auto px-4 py-8">
        {deploymentUrl && <RecentSamples deploymentUrl={deploymentUrl} />}
        {modelName && <UpdateButton modelName={modelName} />}
      </div>
    );
  else if (workflowtype == 'ndb') {
    console.log('update button, ', modelName);
    return (
      <>
        <UsageStats />
        <RecentFeedbacks />
        {modelName && <UpdateButton modelName={modelName} />}
      </>
    );
  }
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <AnalyticsContent />
    </Suspense>
  );
}
