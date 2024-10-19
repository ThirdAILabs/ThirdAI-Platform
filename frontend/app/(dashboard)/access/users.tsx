'use client';
import React, { useState, useEffect } from 'react';
import { Button } from '@mui/material';
import { fetchAllUsers, deleteUserAccount } from '@/lib/backend';
import { UserContext } from '../../user_wrapper';
import { getUsers, User } from '@/utils/apiRequests';

export default function Users() {
  const { user } = React.useContext(UserContext);
  const isGlobalAdmin = user?.global_admin;
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    getUsersData();
  }, []);

  async function getUsersData() {
    const userData = await getUsers();
    if (userData) setUsers(userData);
  }

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
          {isGlobalAdmin ? (
            <Button
              onClick={() => deleteUser(user.name)}
              variant="contained"
              color="error"
              disabled={!isGlobalAdmin}
            >
              Delete User
            </Button>
          ) : (
            <></>
          )}
        </div>
      ))}
    </div>
  );
}
