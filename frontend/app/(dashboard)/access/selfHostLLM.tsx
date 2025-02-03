import React, { useState, useEffect } from 'react';
import {
  Link,
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  getSelfHostedLLM,
  addSelfHostedLLM,
  deleteSelfHostedLLM,
  getAppsUsingLLM,
} from '@/lib/backend';
import type { SelfHostedLLM } from '@/lib/backend';

interface App {
  id: string;
  name: string;
}

export default function SelfHostLLMComponent() {
  const [endpoint, setEndpoint] = useState<SelfHostedLLM | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');
  const [formData, setFormData] = useState<SelfHostedLLM>({
    endpoint: '',
    api_key: '',
  });
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [appsUsingLLM, setAppsUsingLLM] = useState<App[]>([]);
  const [checkingApps, setCheckingApps] = useState(false);

  useEffect(() => {
    fetchEndpoint();
  }, []);

  const fetchEndpoint = async (): Promise<void> => {
    try {
      const response = await getSelfHostedLLM();
      if (response.data?.endpoint && response.data?.api_key) {
        setEndpoint(response.data);
      }
    } catch (error) {
      setError('Failed to fetch endpoint');
    }
  };

  const handleDeleteClick = async () => {
    setCheckingApps(true);
    try {
      const apps = await getAppsUsingLLM();
      console.log('Apps using this LLM endpoint:', apps);
      setAppsUsingLLM(apps);
      setDeleteDialogOpen(true);
    } catch (error) {
      setError('Failed to check apps using this endpoint');
    } finally {
      setCheckingApps(false);
    }
  };

  const handleConfirmDelete = async () => {
    try {
      await deleteSelfHostedLLM();
      setSuccess('Endpoint deleted successfully');
      setEndpoint(null);
      setDeleteDialogOpen(false);
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to delete endpoint');
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

  const handleInputChange =
    (field: keyof SelfHostedLLM) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    };

  return (
    <div>
      <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
        <Alert severity="info" sx={{ mb: 3 }}>
          Ensure your self-hosted API endpoint is compatible with OpenAI API streaming/generate
          endpoint format:{' '}
          <Link
            href="https://platform.openai.com/docs/api-reference/making-requests"
            target="_blank"
            rel="noopener noreferrer"
          >
            OpenAI API Request Documentation
          </Link>
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
                  onClick={handleDeleteClick}
                  disabled={checkingApps}
                  sx={{ color: 'error.main' }}
                >
                  {checkingApps ? <CircularProgress size={24} /> : <DeleteIcon />}
                </IconButton>
              </ListItemSecondaryAction>
            </ListItem>
          </List>
        </Paper>
      )}

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete LLM Endpoint</DialogTitle>
        <DialogContent>
          {appsUsingLLM.length > 0 ? (
            <>
              <Typography variant="body1" sx={{ mb: 2 }}>
                The following apps are currently using this endpoint:
              </Typography>
              <List>
                {appsUsingLLM.map((app) => (
                  <ListItem key={app.id}>
                    <ListItemText primary={app.name} />
                  </ListItem>
                ))}
              </List>
              <Typography variant="body2" color="error">
                Deleting this endpoint will affect these applications.
              </Typography>
            </>
          ) : (
            <Typography variant="body1">
              Are you sure you want to delete this endpoint?
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleConfirmDelete} color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}
