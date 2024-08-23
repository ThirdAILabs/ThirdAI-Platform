"use client"

import React, { useEffect, useRef, useState } from "react";
import {
    TableHead,
    TableRow,
    TableHeader,
    TableBody,
    Table,
    TableCell
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeploymentStatsTable, useTokenClassificationEndpoints } from "@/lib/backend";

export default function Dashboard() {
  const [system, setSystem] = useState<DeploymentStatsTable>({
    header: ['--', '--'],
    rows: [['--', '--'], ['--', '--'], ['--', '--'], ['--', '--']]
  });

  const [throughput, setThroughput] = useState<DeploymentStatsTable>({
    header: ['--', '--', '--', '--'],
    rows: [['--', '--', '--', '--'], ['--', '--', '--', '--']]
  });

  const { getStats } = useTokenClassificationEndpoints();

  useEffect(() => {
    if (!getStats) {
      return;
    }
    const fetchStats = () => {
      getStats().then(({system, throughput}) => {
        setSystem(system);
        setThroughput(throughput);
      })
    };

    fetchStats();

    // Fetch stats every 2 seconds
    const intervalId = setInterval(fetchStats, 2000);

    // Clean up the interval on component unmount
    return () => {
      clearInterval(intervalId);
    }
  }, [getStats]);

  const table = (tableInfo: DeploymentStatsTable, title: string) => {
    return <Card>
      <CardHeader>
          <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
          <Table>
              <TableHeader>
                  <TableRow>
                      <TableHead>{tableInfo.header[0]}</TableHead>
                      {
                        tableInfo.header.slice(1, tableInfo.header.length).map((h, i) => <TableHead key={i} className="text-right">{h}</TableHead>)
                      }
                  </TableRow>
              </TableHeader>
              <TableBody>
                  {
                    tableInfo.rows.map((row, i) => {
                      return <TableRow key={i}>
                          <TableCell className="font-medium" align="left">{row[0]}</TableCell>
                          {row.slice(1, row.length).map((c, i) => <TableCell key={i} className="font-medium" align="right">{c}</TableCell>)}
                        </TableRow>
                    })
                  }
              </TableBody>
          </Table>
      </CardContent>
    </Card>
  }

  return (
    <>  
        <div className="bg-muted" style={{width: "100%", paddingTop: "10%", display: "flex", justifyContent: "center", height: "100vh"}}>
            <div style={{width: "80%", display: "flex", justifyContent: "center", height: "fit-content"}}>
                {table(system, "System Info")}
                <div style={{width: "30px"}}/>
                {table(throughput, "Throughput")}
            </div>
        </div>
    
    </>
  );
}
