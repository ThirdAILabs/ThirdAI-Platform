'use client';

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
  ChartData,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

interface ChartProps {
  data: ChartData<'line'>;
}

export function UsageDurationChart({ data }: ChartProps) {
  const options: ChartOptions<'line'> = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Daily/Monthly Usage Duration',
      },
    },
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>User Usage Duration</CardTitle>
        <CardDescription>How long users engage with the system</CardDescription>
      </CardHeader>
      <CardContent>
        <Line options={options} data={data} />
      </CardContent>
    </Card>
  );
}

export function UsageFrequencyChart({ data }: ChartProps) {
  const options: ChartOptions<'line'> = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Daily/Monthly Usage Frequency',
      },
    },
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>User Usage Frequency</CardTitle>
        <CardDescription>Number of queries, clicks, upvotes, associates</CardDescription>
      </CardHeader>
      <CardContent>
        <Line options={options} data={data} />
      </CardContent>
    </Card>
  );
}

export function ReformulatedQueriesChart({ data }: ChartProps) {
  const options: ChartOptions<'line'> = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Reformulated Queries Over Time',
      },
    },
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reformulated Queries</CardTitle>
        <CardDescription>How often users reformulate queries</CardDescription>
      </CardHeader>
      <CardContent>
        <Line options={options} data={data} />
      </CardContent>
    </Card>
  );
}
