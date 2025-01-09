import React, { useState, useEffect } from 'react';
import {
  TextField,
  Button,
  Paper,
  Alert,
  Typography,
  CircularProgress,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { getSelfHostedLLM, addSelfHostedLLM, deleteSelfHostedLLM } from '@/lib/backend';
import type { SelfHostedLLM } from '@/lib/backend';

export default function SelfHostLLMComponent() {
  const [endpoint, setEndpoint] = useState<SelfHostedLLM | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');
  const [formData, setFormData] = useState<SelfHostedLLM>({
    endpoint: '',
    api_key: '',
  });

  useEffect(() => {
    fetchEndpoint();
  }, []);

  const fetchEndpoint = async (): Promise<void> => {
    try {
      const response = await getSelfHostedLLM();
      console.log('response', response);
      if (response.data?.endpoint && response.data?.api_key) {
        console.log('response data valid', response.data);
        setEndpoint(response.data);
      }
    } catch (error) {
      setError('Failed to fetch endpoint');
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!formData.endpoint || !formData.api_key) {
      setError('All fields are required');
      return;
    }

    setLoading(true);
    try {
      await addSelfHostedLLM(formData);
      setSuccess('Endpoint added successfully');
      setFormData({ endpoint: '', api_key: '' });
      fetchEndpoint();
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to add endpoint');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (): Promise<void> => {
    try {
      await deleteSelfHostedLLM();
      setSuccess('Endpoint deleted successfully');
      setEndpoint(null);
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to delete endpoint');
    }
  };

  const handleInputChange =
    (field: keyof SelfHostedLLM) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    };

  return (
    <div>
      <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
        <Alert severity="info" sx={{ mb: 3 }}>
          Ensure your self-hosted API endpoint is compatible with OpenAI API streaming/generate
          endpoint format: https://platform.openai.com/docs/api-reference/making-requests
        </Alert>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <Typography variant="subtitle1">API Endpoint</Typography>
            <TextField
              fullWidth
              value={formData.endpoint}
              onChange={handleInputChange('endpoint')}
              placeholder="https://your-api-endpoint.com/v1/chat/completions"
              margin="dense"
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <Typography variant="subtitle1">API Key</Typography>
            <TextField
              fullWidth
              type="password"
              value={formData.api_key}
              onChange={handleInputChange('api_key')}
              placeholder="Enter your API key"
              margin="dense"
            />
          </div>

          <Button
            type="submit"
            variant="contained"
            fullWidth
            disabled={loading}
            startIcon={loading && <CircularProgress size={20} />}
          >
            {loading ? 'Testing...' : 'Add Endpoint'}
          </Button>
        </form>

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

      {endpoint && (
        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Current Integration
          </Typography>
          <List>
            <ListItem divider>
              <ListItemText primary="API Endpoint" secondary={endpoint.endpoint} />
            </ListItem>
            <ListItem>
              <ListItemText
                primary="API Key"
                secondary={`${endpoint.api_key.slice(0, 4)}...${endpoint.api_key.slice(-4)}`}
              />
              <ListItemSecondaryAction>
                <IconButton
                  edge="end"
                  aria-label="delete"
                  onClick={handleDelete}
                  sx={{ color: 'error.main' }}
                >
                  <DeleteIcon />
                </IconButton>
              </ListItemSecondaryAction>
            </ListItem>
          </List>
        </Paper>
      )}
    </div>
  );
}
