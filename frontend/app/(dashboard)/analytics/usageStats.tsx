'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Link from 'next/link';
import { Button } from '@mui/material';
import _ from 'lodash';

function getUrlParams() {
  const url = new URL(window.location.href);
  const params = new URLSearchParams(url.search);
  const userName = params.get('username');
  const modelName = params.get('model_name');
  const model_id = params.get('old_model_id');
  const default_mode = params.get('default');
  return { userName, modelName, model_id, default_mode };
}

export default function UsageStats() {
  const thirdaiPlatformBaseUrl = _.trim(process.env.THIRDAI_PLATFORM_BASE_URL!, '/');
  const grafanaUrl = `${thirdaiPlatformBaseUrl}/grafana`;
  const { model_id, default_mode } = getUrlParams();

  let dashboardInitials;
  if (default_mode === 'search') dashboardInitials = 'fe3m66kjmu0hsa/search-model';
  else dashboardInitials = 'ae7rn25nhxdkwc/chat';

  const panelUrl = `${grafanaUrl}/d-solo/${dashboardInitials}?orgId=1&var-workload=deployment-${model_id}&theme=light`;

  return (
    <div className="px-4">
      <Card>
        <CardHeader>
          <CardTitle>Model Status</CardTitle>
          {/* <CardDescription>Monitor real-time usage and system improvements.</CardDescription> */}
        </CardHeader>
        <CardContent>
          {default_mode === 'search' ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-1">
              <iframe
                src={`${panelUrl}&panelId=1&from=now-6h&to=now&t=${Date.now()}`}
                width="100%"
                height="300"
              ></iframe>
              <iframe
                src={`${panelUrl}&panelId=2&from=now-6h&to=now&t=${Date.now()}`}
                width="100%"
                height="300"
              ></iframe>
              <iframe
                src={`${panelUrl}&panelId=3&from=now-6h&to=now&t=${Date.now()}`}
                width="100%"
                height="300"
              ></iframe>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-1">
              <iframe
                src={`${panelUrl}&panelId=2&from=now-6h&to=now&t=${Date.now()}`}
                width="100%"
                height="300px"
              ></iframe>
              <iframe
                src={`${panelUrl}&panelId=3&from=now-6h&to=now&t=${Date.now()}`}
                width="100%"
                height="300px"
              ></iframe>
              <iframe
                src={`${panelUrl}&panelId=4&from=now-6h&to=now&t=${Date.now()}`}
                width="100%"
                height="300px"
              ></iframe>
            </div>
          )}

          <div className="mt-4 flex justify-center items-center">
            <Link href={grafanaUrl} passHref legacyBehavior>
              <a target="_blank" rel="noopener noreferrer">
                <Button variant="contained">See more system stats</Button>
              </a>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
