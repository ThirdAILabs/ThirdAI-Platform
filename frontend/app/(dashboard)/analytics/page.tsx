'use client'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import RecentSamples from './samples';
import UpdateButton from './updateButton';

export default function AnalyticsPage() {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>System status</CardTitle>
          <CardDescription>Monitor real-time usage and system improvement.</CardDescription>
        </CardHeader>
        <CardContent>
        </CardContent>
      </Card>
      <RecentSamples/>
      <UpdateButton/>
    </>
  );
}
