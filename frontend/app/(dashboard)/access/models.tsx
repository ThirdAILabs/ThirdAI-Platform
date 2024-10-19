'use client';
import React, { useState, useEffect } from 'react';
import { Button } from '@mui/material';
import { updateModelAccessLevel, deleteModel } from '@/lib/backend';
import { UserContext } from '../../user_wrapper';
import ConditionalButton from '@/components/ui/ConditionalButton';
import { getModels, getTeams, getUsers, Model, Team, User } from '@/utils/apiRequests';

export default function Models() {
  // State variables
  const [models, setModels] = useState<Model[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [selectedType, setSelectedType] = useState<
    'Private Model' | 'Protected Model' | 'Public Model' | null
  >(null);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const { user } = React.useContext(UserContext);
  const [modelEditPermissions, setModelEditPermissions] = useState<boolean[]>([]);

  useEffect(() => {
    getModelsData();
  }, []);

  async function getModelsData() {
    const modelData = await getModels();
    if (modelData) setModels(modelData);
  }

  useEffect(() => {
    getUsersData();
  }, []);

  async function getUsersData() {
    const userData = await getUsers();
    if (userData) setUsers(userData);
  }

  useEffect(() => {
    getTeamsData();
  }, [users]);

  async function getTeamsData() {
    const teamData = await getTeams();
    if (teamData) setTeams(teamData);
  }

  // Function to handle model type change
  const handleModelTypeChange = async (index: number) => {
    if (!selectedType) return;

    try {
      const model = models[index];
      const model_identifier = `${model.owner}/${model.name}`;
      let access_level: 'private' | 'protected' | 'public' = 'private';
      let team_id: string | undefined;

      switch (selectedType) {
        case 'Private Model':
          access_level = 'private';
          break;
        case 'Protected Model':
          access_level = 'protected';
          team_id = selectedTeam || undefined;
          break;
        case 'Public Model':
          access_level = 'public';
          break;
      }
      await updateModelAccessLevel(model_identifier, access_level, team_id);
      await getModelsData();

      setEditingIndex(null);
      setSelectedType(null);
      setSelectedTeam(null);
    } catch (error) {
      console.error('Failed to update model access level', error);
      alert('Failed to update model access level' + error);
    }
  };

  // Function to handle model deletion
  const handleDeleteModel = async (index: number) => {
    const model = models[index];
    const model_identifier = `${model.owner}/${model.name}`;

    try {
      const isConfirmed = window.confirm(
        `Are you sure you want to delete the model "${model.name}"?`
      );
      if (!isConfirmed) return;

      await deleteModel(model_identifier);
      await getModelsData();
    } catch (error) {
      console.error('Failed to delete model', error);
      alert('Failed to delete model: ' + error);
    }
  };

  //The function decides if the user is allowed to make changes in the access level or delete the model out of n-models.
  const getModelEditPermissions = () => {
    const permissions = [];
    for (let index = 0; index < models.length; index++) {
      const model = models[index];
      if (user?.global_admin) {
        permissions.push(true);
        continue;
      }
      if (model.owner === user?.username) permissions.push(true);
      else {
        let value = false;
        if (user?.teams && model.type === 'Protected Model') {
          for (let itr = 0; itr < user?.teams.length; itr++) {
            if (user?.teams[itr].team_id === model.team && user.teams[itr].role === 'team_admin') {
              value = true;
              break;
            }
          }
          permissions.push(value);
        } else permissions.push(false);
      }
    }
    setModelEditPermissions(permissions);
  };

  useEffect(() => {
    getModelEditPermissions();
  }, [models]);

  return (
    <div className="mb-12">
      <h3 className="text-xl font-semibold text-gray-800 mb-4">Models</h3>
      <table className="w-full bg-white rounded-lg shadow-md overflow-hidden">
        <thead className="bg-gray-100">
          <tr>
            <th className="py-3 px-4 text-left text-gray-700">Model Name</th>
            <th className="py-3 px-4 text-left text-gray-700">Model Type</th>
            <th className="py-3 px-4 text-left text-gray-700">Access Details</th>
            <th className="py-3 px-4 text-left text-gray-700">Edit Model Access</th>
            <th className="py-3 px-4 text-left text-gray-700">Delete Model</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model, index) => (
            <tr key={index} className="border-t">
              <td className="py-3 px-4 text-gray-800">{model.name}</td>
              <td className="py-3 px-4 text-gray-800">{model.type}</td>
              <td className="py-3 px-4 text-gray-800">
                {model.type === 'Private Model' && (
                  <div>
                    <div>Owner: {model.owner}</div>
                    <div>Users: {model.users?.join(', ') || 'None'}</div>
                  </div>
                )}
                {model.type === 'Protected Model' && (
                  <div>
                    <div>Owner: {model.owner}</div>
                    <div>Team: {teams.find((team) => team.id === model.team)?.name || 'None'}</div>
                  </div>
                )}
                {model.type === 'Public Model' && <div>Owner: {model.owner}</div>}
              </td>
              <td className="py-3 px-4">
                {editingIndex === index ? (
                  <div className="flex flex-col space-y-2">
                    <select
                      value={selectedType || model.type}
                      onChange={(e) =>
                        setSelectedType(
                          e.target.value as 'Private Model' | 'Protected Model' | 'Public Model'
                        )
                      }
                      className="border border-gray-300 rounded px-4 py-2"
                    >
                      <option value="Private Model">Private Model</option>
                      <option value="Protected Model">Protected Model</option>
                      <option value="Public Model">Public Model</option>
                    </select>

                    {selectedType === 'Protected Model' && (
                      <select
                        value={selectedTeam || ''}
                        onChange={(e) => setSelectedTeam(e.target.value)}
                        className="border border-gray-300 rounded px-4 py-2"
                      >
                        <option value="" disabled>
                          Select Team
                        </option>
                        {teams.map((team) => (
                          <option key={team.id} value={team.id}>
                            {team.name}
                          </option>
                        ))}
                      </select>
                    )}
                    <div className="flex space-x-2 mt-2">
                      <Button
                        onClick={() => handleModelTypeChange(index)}
                        className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
                      >
                        Confirm
                      </Button>
                      <Button
                        onClick={() => setEditingIndex(null)}
                        className="bg-gray-500 text-white px-4 py-2 rounded hover:bg-gray-600"
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <ConditionalButton
                    onClick={() => setEditingIndex(index)}
                    isDisabled={!modelEditPermissions[index]}
                    tooltipMessage="Global Admin, Model owner and Team Admin can change access"
                    variant="contained"
                  >
                    Change Access
                  </ConditionalButton>
                )}
              </td>

              <td className="py-3 px-4">
                <ConditionalButton
                  onClick={() => handleDeleteModel(index)}
                  isDisabled={!modelEditPermissions[index]}
                  tooltipMessage="Global Admin, Model owner and Team Admin can delete"
                  variant="contained"
                  color="error"
                >
                  Delete
                </ConditionalButton>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
