import React, { useState, useEffect, use } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material';
import {
  fetchAllUsers,
  deleteUserAccount,
  promoteUserToGlobalAdmin,
  verifyUser,
} from '@/lib/backend';
import { UserContext } from '../../user_wrapper';
import { getUsers, User } from '@/utils/apiRequests';
import UserCreationForm from './UserCreationForm';
import ConditionalButton from '@/components/ui/ConditionalButton';

export default function Users() {
  const { user } = React.useContext(UserContext);
  const isGlobalAdmin = user?.global_admin;
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isDeleteDialogOpen, setDeleteDialogOpen] = useState(false);

  useEffect(() => {
    getUsersData();
  }, []);

  async function getUsersData() {
    const userData = await getUsers();
    if (userData) setUsers(userData);
  }

  const handleOpenDeleteDialog = (user: User) => {
    setSelectedUser(user);
    setDeleteDialogOpen(true);
  };

  const handleCloseDeleteDialog = () => {
    setSelectedUser(null);
    setDeleteDialogOpen(false);
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    try {
      await deleteUserAccount(selectedUser.email);
      await getUsersData();
      setDeleteDialogOpen(false);
    } catch (error) {
      console.error('Failed to delete user', error);
      alert('Failed to delete user: ' + error);
    }
  };

  const handleVerifyUser = async (email: string) => {
    try {
      await verifyUser(email);
      await getUsersData();
    } catch (error: any) {
      console.error('Failed to verify user', error);
      alert(error.response?.data?.message || 'Failed to verify user');
    }
  };

  const handlePromotion = async (userName: string) => {
    try {
      const user = users.find((u) => u.name === userName);
      if (!user) {
        console.error('User not found');
        return;
      }

      const isConfirmed = window.confirm(
        `Are you sure you want to promote the "${userName}" to Global Admin?`
      );
      if (!isConfirmed) return;

      await promoteUserToGlobalAdmin(user.email);
      await getUsers();
    } catch (error) {
      console.error('Failed to promote user', error);
      alert('Failed to promote user: ' + error);
    }
  };
  return (
    <div className="mb-12">
      {isGlobalAdmin && <UserCreationForm onUserCreated={getUsersData} />}

      <h3 className="text-xl font-semibold text-gray-800 mb-4">Users</h3>
      {users.map((user, index) => (
        <div key={index} className=" p-4 rounded-lg shadow-md mb-8 border">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex flex-wrap gap-3">
                <h4 className="text-lg font-semibold text-gray-800">{user.name}</h4>
                {user.is_deactivated && (
                  <h4 className="text-sm text-gray-800 bg-gray-300 rounded-2xl px-2 py-1 text-center max-w-26 border border-gray-400">
                    Deactivated
                  </h4>
                )}
              </div>
              <div className="text-gray-700 mb-2">Role: {user.role}</div>
              <div className="text-gray-700 mb-2">
                Status: {user.verified ? 'Verified' : 'Not Verified'}
              </div>
              {user.teams.filter((team) => team.role === 'team_admin').length > 0 && (
                <div className="text-gray-700 mb-2">
                  Admin Teams:{' '}
                  {user.teams
                    .filter((team) => team.role === 'team_admin')
                    .map((team) => team.name)
                    .join(', ')}
                </div>
              )}
              {/* {user.ownedModels.length > 0 && (
                <div className="text-gray-700">Owned Models: {user.ownedModels.join(', ')}</div>
              )} */}
            </div>
            {isGlobalAdmin && (
              <div className="flex gap-2">
                {!user.verified && !user.is_deactivated && (
                  <Button
                    onClick={() => handleVerifyUser(user.email)}
                    variant="contained"
                    color="primary"
                  >
                    Verify User
                  </Button>
                )}
                <Button
                  onClick={() => handleOpenDeleteDialog(user)}
                  variant="contained"
                  color={!user.is_deactivated ? 'warning' : 'error'}
                  className="min-w-36"
                >
                  {!user.is_deactivated ? 'Deactivate User' : 'Delete User'}
                </Button>
              </div>
            )}
          </div>
          {user.ownedModels.length > 0 && (
            <div className="text-gray-700 flex flex-wrap gap-2">
              Owned Models:{' '}
              {user.ownedModels.map((model, index) => (
                <span>{index < user.ownedModels.length - 1 ? model.name + ', ' : model.name}</span>
              ))}
            </div>
          )}
          {isGlobalAdmin && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '30%' }}>
              {user.role !== 'Global Admin' && !user.is_deactivated && (
                <Button
                  onClick={() => handlePromotion(user.name)}
                  variant="contained"
                  color="success"
                >
                  Promote user to Global Admin
                </Button>
              )}
            </div>
          )}
        </div>
      ))}
      {/* Delete Confirmation Dialog */}
      {selectedUser?.is_deactivated ? (
        <Dialog open={isDeleteDialogOpen} onClose={handleCloseDeleteDialog}>
          <DialogTitle>
            Are you sure you want to delete <strong>{selectedUser.name}</strong>?
          </DialogTitle>
          <DialogContent>
            <Typography>
              {selectedUser.name} currently owns <strong>{selectedUser?.ownedModels.length}</strong>{' '}
              models.
              <br />
              Deleting {selectedUser.name} will also remove their models. <br />
              Please transfer model ownership before proceeding to avoid data loss.
            </Typography>
          </DialogContent>
          <DialogActions>
            <div className="justify-end flex flex-row gap-3">
              <Button onClick={handleCloseDeleteDialog} color="secondary">
                Cancel
              </Button>
              <ConditionalButton
                onClick={handleDeleteUser}
                isDisabled={
                  selectedUser.ownedModels.find(
                    (model) => model.access_level === 'protected' || model.access_level === 'public'
                  ) !== undefined
                }
                tooltipMessage={`Please change the ownership of public and protected models owned by ${selectedUser.name}`}
                color="error"
              >
                Delete User
              </ConditionalButton>
            </div>
          </DialogActions>
        </Dialog>
      ) : (
        // Deactivate confirmation dialog box
        selectedUser && (
          <Dialog open={isDeleteDialogOpen} onClose={handleCloseDeleteDialog}>
            <DialogTitle>Confirm Deactivation</DialogTitle>
            <DialogContent>
              <Typography>
                Are you sure you want to deactivate the user <strong>{selectedUser?.name}</strong>
              </Typography>
            </DialogContent>
            <DialogActions>
              <Button onClick={handleCloseDeleteDialog} color="secondary">
                No
              </Button>
              <Button onClick={handleDeleteUser} color="error">
                Yes
              </Button>
            </DialogActions>
          </Dialog>
        )
      )}
    </div>
  );
}
