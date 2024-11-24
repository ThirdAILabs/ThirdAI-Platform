import React, { useState } from 'react';
import { TextField, Button, Paper, Typography, Box, Alert, Collapse } from '@mui/material';
import { addUser } from '@/lib/backend';

interface UserCreationFormProps {
  onUserCreated: () => void;
}

const UserCreationForm: React.FC<UserCreationFormProps> = ({ onUserCreated }) => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
  });
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      const response = await addUser(formData);
      setFormData({ username: '', email: '', password: '' });
      setSuccessMessage(response.message);
      setErrorMessage('');
      onUserCreated();
      // Clear success message after 5 seconds
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (error: any) {
      setErrorMessage(error.response?.data?.message || 'Error creating user');
      setSuccessMessage('');
    }
  };

  return (
    <Paper elevation={2} sx={{ p: 3, mb: 4, maxWidth: '100%' }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Create New User
      </Typography>
      <Collapse in={!!successMessage}>
        <Alert severity="success" sx={{ mb: 2 }}>
          {successMessage}
        </Alert>
      </Collapse>
      <Collapse in={!!errorMessage}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMessage}
        </Alert>
      </Collapse>
      <Box
        component="form"
        onSubmit={handleSubmit}
        sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
      >
        <TextField
          label="Username"
          value={formData.username}
          onChange={(e) => setFormData((prev) => ({ ...prev, username: e.target.value }))}
          required
          size="small"
        />
        <TextField
          label="Email"
          type="email"
          value={formData.email}
          onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
          required
          size="small"
        />
        <TextField
          label="Password"
          type="password"
          value={formData.password}
          onChange={(e) => setFormData((prev) => ({ ...prev, password: e.target.value }))}
          required
          size="small"
        />
        <Button type="submit" variant="contained" color="primary" sx={{ mt: 1 }}>
          Create User
        </Button>
      </Box>
    </Paper>
  );
};

export default UserCreationForm;
