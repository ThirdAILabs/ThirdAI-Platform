'use client';
import React, { useState, useEffect } from 'react';
import { TextField, Button } from '@mui/material';

export default function OpenAIKey() {
  const [apiKey, setApiKey] = useState('');
  const [newApiKey, setNewApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    fetchApiKey();
  }, []);

  const fetchApiKey = async () => {
    try {
      const response = await fetch('/endpoints/get_openai_key');
      const data = await response.json();
      if (data.apiKey) {
        setApiKey(data.apiKey); // set masked API key
      }
    } catch (error) {
      console.error('Failed to fetch API key', error);
      alert('Failed to fetch API key: ' + error);
    }
  };

  const handleSave = async () => {
    if (!newApiKey) {
      alert('Please enter a new OpenAI API Key');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('/endpoints/change_openai_key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ newApiKey }),
      });

      const data = await response.json();
      if (data.success) {
        setSuccessMessage('OpenAI API Key successfully updated!');
        setApiKey(`sk-${newApiKey.slice(-4)}`);
        setNewApiKey(''); // clear the openai key field
      } else {
        alert('Error updating API Key');
      }
    } catch (error) {
      console.error('Failed to update API key', error);
      alert('Failed to update API key: ' + error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-100 p-6 rounded-lg shadow-md mb-8">
      <h4 className="text-lg font-semibold text-gray-800">Change OpenAI API Key</h4>
      <div className="mt-4">
        <label className="block text-gray-700">Current Organization OpenAI API Key (masked):</label>
        <p className="bg-gray-200 p-2 rounded">{apiKey || 'Loading...'}</p>
      </div>
      <div className="mt-4">
        <label className="block text-gray-700">New OpenAI API Key:</label>
        <TextField
          type="text"
          placeholder="sk-..."
          value={newApiKey}
          onChange={(e) => setNewApiKey(e.target.value)}
          className="border border-gray-300 rounded px-4 py-2 w-full"
        />
      </div>
      <Button
        onClick={handleSave}
        variant="contained"
        className={`mt-4 ${loading ? 'cursor-not-allowed' : ''}`}
        disabled={loading}
      >
        {loading ? 'Saving...' : 'Save'}
      </Button>
      {successMessage && <p className="text-green-500 mt-4">{successMessage}</p>}
    </div>
  );
}
