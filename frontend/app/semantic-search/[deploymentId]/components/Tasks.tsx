import { DropdownMenuContent } from '@/components/ui/dropdown-menu';
import React from 'react';
import styled from 'styled-components';

// Types based on Python enums from backend
export enum TaskStatus {
  NOT_STARTED = 'not_started',
  IN_PROGRESS = 'in_progress',
  FAILED = 'failed',
  COMPLETE = 'complete',
}

export enum TaskAction {
  INSERT = 'insert',
  DELETE = 'delete',
}

export interface Task {
  status: TaskStatus;
  action: TaskAction;
  last_modified: string;
  data: {
    sources?: string[];
    [key: string]: any;
  };
  message: string;
}

interface TasksProps {
  tasks: Record<string, Task>;
}

const TaskItem = styled.div`
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: white;
  margin-bottom: 8px;
  &:last-child {
    margin-bottom: 0;
  }
`;

const TaskHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
`;

const StatusBadge = styled.span<{ status: TaskStatus }>`
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background-color: ${(props) => {
    switch (props.status) {
      case TaskStatus.NOT_STARTED:
        return '#e0e0e0';
      case TaskStatus.IN_PROGRESS:
        return '#90caf9';
      case TaskStatus.COMPLETE:
        return '#a5d6a7';
      case TaskStatus.FAILED:
        return '#ef9a9a';
      default:
        return '#e0e0e0';
    }
  }};
  color: ${(props) => {
    switch (props.status) {
      case TaskStatus.NOT_STARTED:
        return '#666';
      case TaskStatus.IN_PROGRESS:
        return '#1565c0';
      case TaskStatus.COMPLETE:
        return '#2e7d32';
      case TaskStatus.FAILED:
        return '#c62828';
      default:
        return '#666';
    }
  }};
`;

const ActionBadge = styled.span<{ action: TaskAction }>`
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background-color: ${(props) =>
    props.action === TaskAction.INSERT ? '#e8eaf6' : '#fff3e0'};
  color: ${(props) =>
    props.action === TaskAction.INSERT ? '#283593' : '#e65100'};
`;

const Title = styled.div`
  font-weight: bold;
  margin-bottom: 8px;
`;

const Message = styled.div`
  font-size: 14px;
  margin-top: 8px;
`;

const Sources = styled.div`
  font-size: 12px;
  color: #666;
  margin-top: 8px;
`;

const NoTasks = styled.div`
  text-align: center;
  color: #666;
  padding: 12px;
`;

export default function Tasks({ tasks }: TasksProps) {
  return (
    <DropdownMenuContent className="min-w-[300px] p-4">
      <Title>Tasks</Title>
      {Object.entries(tasks).map(([taskId, task]) => (
        <TaskItem key={taskId}>
          <TaskHeader>
            <div>
              <StatusBadge status={task.status}>{task.status}</StatusBadge>{' '}
              <ActionBadge action={task.action}>{task.action}</ActionBadge>
            </div>
            <StatusBadge status={task.status} style={{ opacity: 0.7 }}>
              {new Date(task.last_modified).toLocaleString()}
            </StatusBadge>
          </TaskHeader>
          {task.message && <Message>{task.message}</Message>}
          {task.data.sources && (
            <Sources>Sources: {task.data.sources.join(', ')}</Sources>
          )}
        </TaskItem>
      ))}
      {Object.keys(tasks).length === 0 && <NoTasks>No tasks</NoTasks>}
    </DropdownMenuContent>
  );
}
