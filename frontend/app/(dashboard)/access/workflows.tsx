'use client';
import React, { useState, useEffect } from 'react';
import { fetchWorkflows } from '@/lib/backend';

type Workflow = {
  name: string;
  type: string;
  status: string;
  created_by: {
    username: string;
    email: string;
  };
  models: {
    model_name: string;
    type: string;
    publish_date: string;
  }[];
};

export default function Workflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  useEffect(() => {
    getWorkflows();
  }, []);

  const getWorkflows = async () => {
    try {
      const fetchedWorkflows = await fetchWorkflows();
      setWorkflows(fetchedWorkflows);
    } catch (error) {
      console.error('Failed to fetch workflows', error);
      alert('Failed to fetch workflows' + error);
    }
  };

  return (
    <div className="mb-12">
      <h3 className="text-xl font-semibold text-gray-800 mb-4">Workflows</h3>
      <table className="w-full bg-white rounded-lg shadow-md overflow-hidden">
        <thead className="bg-gray-100">
          <tr>
            <th className="py-3 px-4 text-left text-gray-700">Workflow Name</th>
            <th className="py-3 px-4 text-left text-gray-700">Type</th>
            <th className="py-3 px-4 text-left text-gray-700">Status</th>
            <th className="py-3 px-4 text-left text-gray-700">Created By</th>
            <th className="py-3 px-4 text-left text-gray-700">Models</th>
          </tr>
        </thead>
        <tbody>
          {workflows.map((workflow, index) => (
            <tr key={index} className="border-t">
              <td className="py-3 px-4 text-gray-800">{workflow.name}</td>
              <td className="py-3 px-4 text-gray-800">{workflow.type}</td>
              <td className="py-3 px-4 text-gray-800">{workflow.status}</td>
              <td className="py-3 px-4 text-gray-800">
                <div>Username: {workflow.created_by.username}</div>
                <div>Email: {workflow.created_by.email}</div>
              </td>
              <td className="py-3 px-4 text-gray-800">
                {workflow.models.length > 0 ? (
                  workflow.models.map((model, i) => (
                    <div key={i} className="mb-2">
                      <div>Model Name: {model.model_name}</div>
                      <div>Type: {model.type}</div>
                      <div>Published On: {model.publish_date}</div>
                    </div>
                  ))
                ) : (
                  <div>No models associated with this workflow</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
