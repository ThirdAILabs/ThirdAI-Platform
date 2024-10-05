'use client';
import React, { useState, useEffect } from 'react';
import { Button } from '@mui/material';
import { fetchAllUsers, deleteUserAccount } from '@/lib/backend';

type UserTeam = {
  id: string;
  name: string;
  role: 'Member' | 'team_admin' | 'Global Admin';
};

type User = {
  id: string;
  name: string;
  email: string;
  role: 'Member' | 'Team Admin' | 'Global Admin';
  teams: UserTeam[];
  ownedModels: string[];
};

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    getUsers();
  }, []);

  const getUsers = async () => {
    try {
      const response = await fetchAllUsers();
      console.log('Fetched Users:', response.data);
      const userData = response.data.map(
        (user): User => ({
          id: user.id,
          name: user.username,
          email: user.email,
          role: user.global_admin ? 'Global Admin' : 'Member',
          teams: user.teams.map((team) => ({
            id: team.team_id,
            name: team.team_name,
            role: team.role,
          })),
          ownedModels: [], // This should be populated with actual data if available
        })
      );
      setUsers(userData);
    } catch (error) {
      console.error('Failed to fetch users', error);
      alert('Failed to fetch users' + error);
    }
  };

  const deleteUser = async (userName: string) => {
    try {
      const user = users.find((u) => u.name === userName);
      if (!user) {
        console.error('User not found');
        return;
      }

      const isConfirmed = window.confirm(`Are you sure you want to delete the user "${userName}"?`);
      if (!isConfirmed) return;

      await deleteUserAccount(user.email);
      await getUsers(); // Refresh the user list
    } catch (error) {
      console.error('Failed to delete user', error);
      alert('Failed to delete user: ' + error);
    }
  };

  return (
    <div className="mb-12">
      <h3 className="text-xl font-semibold text-gray-800 mb-4">Users</h3>
      {users.map((user, index) => (
        <div key={index} className="bg-gray-100 p-4 rounded-lg shadow-md mb-8">
          <h4 className="text-lg font-semibold text-gray-800">{user.name}</h4>
          <div className="text-gray-700 mb-2">Role: {user.role}</div>
          {user.teams.filter((team) => team.role === 'team_admin').length > 0 && (
            <div className="text-gray-700 mb-2">
              Admin Teams:{' '}
              {user.teams
                .filter((team) => team.role === 'team_admin')
                .map((team) => team.name)
                .join(', ')}
            </div>
          )}
          {user.ownedModels.length > 0 && (
            <div className="text-gray-700">Owned Models: {user.ownedModels.join(', ')}</div>
          )}
          <Button onClick={() => deleteUser(user.name)} variant="contained" color="error">
            Delete User
          </Button>
        </div>
      ))}
    </div>
  );
}
