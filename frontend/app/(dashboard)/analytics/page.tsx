'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import RecentSamples from './samples';
import UpdateButton from './updateButton';
import { UsageDurationChart, UsageFrequencyChart, ReformulatedQueriesChart } from './charts';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button } from '@mui/material';
import _ from 'lodash';

export default function AnalyticsPage() {
  const [isClient, setIsClient] = useState(false);

  // Ensure that the component only runs on the client
  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return null; // Return null on the first render to avoid hydration mismatch
  }

  const usageDurationData = {
    labels: ['7/17-7/20', '7/18-7/21', '7/22-7/25', '7/26-7/29', '7/30-8/2', '8/3-8/6', '8/7-8/11'],
    datasets: [
      {
        label: 'Hours per Day',
        data: [2.5, 3.2, 2.8, 3.5, 4.1, 3.9, 4.5],
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      },
      {
        label: 'Hours per Month',
        data: [75, 90, 86, 105, 128, 121, 135],
        borderColor: 'rgb(54, 162, 235)',
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
      },
    ],
  };

  const usageFrequencyData = {
    labels: ['7/17-7/20', '7/18-7/21', '7/22-7/25', '7/26-7/29', '7/30-8/2', '8/3-8/6', '8/7-8/11'],
    datasets: [
      {
        label: 'Queries per Day',
        data: [25, 30, 28, 35, 40, 39, 45],
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
      },
      {
        label: 'Clicks per Day',
        data: [15, 18, 20, 22, 24, 26, 28],
        borderColor: 'rgb(153, 102, 255)',
        backgroundColor: 'rgba(153, 102, 255, 0.2)',
      },
      {
        label: 'Upvotes per Day',
        data: [16, 13, 16, 13, 11, 10, 8],
        borderColor: 'rgb(255, 159, 64)',
        backgroundColor: 'rgba(255, 159, 64, 0.2)',
      },
      {
        label: 'Associates per Day',
        data: [5, 6, 5, 6, 7, 6, 7],
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      },
    ],
  };

  const reformulatedQueriesData = {
    labels: ['7/17-7/20', '7/18-7/21', '7/22-7/25', '7/26-7/29', '7/30-8/2', '8/3-8/6', '8/7-8/11'],
    datasets: [
      {
        label: 'Reformulated Queries',
        data: [18, 15, 17, 14, 13, 12, 10],
        borderColor: 'rgb(255, 205, 86)',
        backgroundColor: 'rgba(255, 205, 86, 0.2)',
      },
    ],
  };

  const thirdaiPlatformBaseUrl = _.trim(process.env.thirdai_platform_services_URL!, '/');
  const grafanaUrl = `${thirdaiPlatformBaseUrl}/grafana`;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
          <CardDescription>Monitor real-time usage and system improvements.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <UsageDurationChart data={usageDurationData} />
            <UsageFrequencyChart data={usageFrequencyData} />
            <ReformulatedQueriesChart data={reformulatedQueriesData} />
          </div>

          <div className="mt-4 flex justify-center items-center">
            <Link href={grafanaUrl} passHref legacyBehavior>
              <a target="_blank" rel="noopener noreferrer">
                <Button variant="contained">See more system stats</Button>
              </a>
            </Link>
          </div>
        </CardContent>
      </Card>

      <div className="mt-6">
        <h2 className="text-lg font-semibold mb-2">Usage Duration Trend</h2>
        <p className="mb-4">
          Over the past few months, we&apos;ve observed a steady increase in the duration users
          spend on the system. This indicates that users find the search system increasingly
          valuable and are willing to engage with it for longer periods.
        </p>

        <h2 className="text-lg font-semibold mb-2">User Usage Frequency</h2>
        <p className="mb-4">
          The frequency with which users interact with the system has remained relatively stable,
          with a slight upward trend. This consistency shows that users continue to rely on the
          search system regularly.
        </p>

        <h2 className="text-lg font-semibold mb-2">Reformulated Queries</h2>
        <p className="mb-4">
          While the number of reformulated queries fluctuates, there&apos;s an overall downward
          trend. This suggests that users are becoming more adept at finding the information they
          need on the first attempt, indicating improved search accuracy and user satisfaction.
        </p>
      </div>

      <RecentSamples />
      <UpdateButton />
    </>
  );
}
