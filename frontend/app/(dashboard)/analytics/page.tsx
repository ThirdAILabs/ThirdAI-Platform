'use client';
import RecentFeedbacks from './recentFeedbacks';
import UpdateButton from './updateButton';
import ModelUpdate from './ModelUpdate';
import UpdateButtonNDB from './updateButtonNDB';
import UsageStats from './usageStats';
import UsageStatsUDT from './usageStatsUDT';
import { useEffect, useState, Suspense, use } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  getWorkflowDetails,
  deploymentBaseUrl,
  useTokenClassificationEndpoints,
} from '@/lib/backend';
import _ from 'lodash';
import { Workflow, fetchWorkflows } from '@/lib/backend';

function AnalyticsContent() {
  const [isClient, setIsClient] = useState(false);
  const searchParams = useSearchParams();
  const workflowid = searchParams.get('id');
  const [deploymentUrl, setDeploymentUrl] = useState<string | undefined>();
  const [modelName, setModelName] = useState<string>('');
  const [username, setUsername] = useState<string>('');
  const [workflowtype, setWorkflowType] = useState<string>('');
  const [deployStatus, setDeployStatus] = useState<string>('not_started');
  const [tags, setTags] = useState<string[]>([]);
  useEffect(() => {
    setIsClient(true);

    const init = async () => {
      if (workflowid) {
        try {
          const workflowDetails = await getWorkflowDetails(workflowid);

          console.log('workflowDetails', workflowDetails);
          setWorkflowType(workflowDetails.data.type);

          // Set deploy status
          setDeployStatus(workflowDetails.data.deploy_status);

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

    getWorkflows();
  }, []);

  const workflowNames = workflows.map((workflow) => workflow.model_name);

  if (!isClient) {
    return null; // Return null on the first render to avoid hydration mismatch
  }

  if (workflowtype == 'udt')
    return (
      <div className="container mx-auto px-4 py-8">
        {modelName && deploymentUrl && (
          <>
            <UsageStatsUDT />
            <div className="mt-6">
              <ModelUpdate
                username={username}
                modelName={modelName}
                deploymentUrl={deploymentUrl}
                workflowNames={workflowNames}
                deployStatus={deployStatus}
              />
            </div>
          </>
        )}
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
