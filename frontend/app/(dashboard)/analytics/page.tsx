'use client';
import RecentSamples from './samples';
import RecentFeedbacks from './recentFeedbacks';
import UpdateButton from './updateButton';
import UpdateButtonNDB from './updateButtonNDB';
import UsageStats from './usageStats';
import { UsageDurationChart, UsageFrequencyChart, ReformulatedQueriesChart } from './charts';
import { useEffect, useState, Suspense } from 'react';
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
          if (
            workflowDetails.data.type === 'enterprise-search' &&
            workflowDetails.data.dependencies?.length > 0
          ) {
            // For enterprise-search, use the first dependency's details
            const firstDependency = workflowDetails.data.dependencies[0];
            console.log('firstDependency', firstDependency);
            console.log(`here is: ${deploymentBaseUrl}/${firstDependency.model_id}`);
            setDeploymentUrl(`${deploymentBaseUrl}/${firstDependency.model_id}`);
            setModelName(firstDependency.model_name);
            setUsername(firstDependency.username);
          } else {
            // For other types, use the original logic
            console.log(`here is: ${deploymentBaseUrl}/${workflowDetails.data.model_id}`);
            setDeploymentUrl(`${deploymentBaseUrl}/${workflowDetails.data.model_id}`);
            setModelName(workflowDetails.data.model_name);
            setUsername(workflowDetails.data.username);
          }
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
  else if (workflowtype == 'ndb' || workflowtype == 'enterprise-search') {
    console.log('update button, ', modelName);
    return (
      <>
        <UsageStats />
        <RecentFeedbacks username={username} modelName={modelName} />
        {modelName && <UpdateButtonNDB modelName={modelName} />}
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
