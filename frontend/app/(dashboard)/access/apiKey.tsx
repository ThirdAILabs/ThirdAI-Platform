import React, { useState, useEffect } from 'react';
import {
  TextField,
  Button,
  Tab,
  Tabs,
  Paper,
  Alert,
  Box,
  Typography,
  CircularProgress,
} from '@mui/material';
import SelfHostLLM from './selfHostLLM';

interface APIResponse {
  apiKey?: string;
  success?: boolean;
  message?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

function TabPanel({ children, value, index, ...other }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`llm-tabpanel-${index}`}
      aria-labelledby={`llm-tab-${index}`}
      {...other}
    >
      {value === index && <Box>{children}</Box>}
    </div>
  );
}

export default function LLMManagement() {
  const [apiKey, setApiKey] = useState<string>('');
  const [newApiKey, setNewApiKey] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [success, setSuccess] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [tabValue, setTabValue] = useState<number>(0);

  useEffect(() => {
    fetchApiKey();
  }, []);

  const fetchApiKey = async (): Promise<void> => {
    try {
      const response = await fetch('/endpoints/get_openai_key');
      const data: APIResponse = await response.json();
      if (data.apiKey) {
        setApiKey(data.apiKey);
      }
    } catch (error) {
      setError('Failed to fetch API key');
    }
  };

  const handleSave = async (): Promise<void> => {
    if (!newApiKey) {
      setError('Please enter a new OpenAI API Key');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/endpoints/change_openai_key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newApiKey }),
      });

      const data: APIResponse = await response.json();
      if (data.success) {
        setSuccess('OpenAI API Key updated successfully');
        setApiKey(`sk-${newApiKey.slice(-4)}`);
        setNewApiKey('');
      } else {
        throw new Error(data.message || 'Error updating API Key');
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update API key');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number): void => {
    setTabValue(newValue);
  };

  return (
    <div>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tabValue} onChange={handleTabChange} centered>
          <Tab label="OpenAI" />
          <Tab label="Self-Hosted" />
        </Tabs>
      </Box>

      <TabPanel value={tabValue} index={0}>
        <Paper elevation={1} sx={{ p: 3, mb: 2 }}>
          <div style={{ marginBottom: '20px' }}>
            <Typography variant="subtitle1">Current OpenAI API Key:</Typography>
            <Paper variant="outlined" sx={{ p: 1, bgcolor: 'grey.100' }}>
              {apiKey || 'Loading...'}
            </Paper>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <Typography variant="subtitle1">New OpenAI API Key:</Typography>
            <TextField
              type="password"
              fullWidth
              placeholder="sk-..."
              value={newApiKey}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewApiKey(e.target.value)}
              margin="dense"
            />
          </div>

          <Button
            variant="contained"
            fullWidth
            onClick={handleSave}
            disabled={loading}
            startIcon={loading && <CircularProgress size={20} />}
          >
            {loading ? 'Saving...' : 'Save'}
          </Button>

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
          {success && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {success}
            </Alert>
          )}
        </Paper>
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <SelfHostLLM />
      </TabPanel>
    </div>
  );
}
