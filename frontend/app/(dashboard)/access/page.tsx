'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  fetchAllModels,
  fetchAllTeams,
  fetchAllUsers,
  updateModelAccessLevel,
  deleteModel,
  createTeam,
  addUserToTeam,
  assignTeamAdmin,
  deleteUserFromTeam,
  deleteTeamById,
  removeTeamAdmin,
  deleteUserAccount,
  Workflow,
  fetchWorkflows,
} from '@/lib/backend';
import { useContext } from 'react';
import { UserContext } from '../../user_wrapper';
import AutocompleteInput from '@/components/ui/AutocompleteInput';
import { TextField, Button } from '@mui/material';
import DropdownMenu from '@/components/ui/dropDownMenu';
// Define types for the models, teams, and users
type Model = {
  name: string;
  type: 'Private Model' | 'Protected Model' | 'Public Model';
  owner: string;
  users?: string[];
  team?: string;
  teamAdmin?: string;
  domain: string;
  latency: string;
  modelId: string;
  numParams: string;
  publishDate: string;
  size: string;
  sizeInMemory: string;
  subType: string;
  thirdaiVersion: string;
  trainingTime: string;
};

type Team = {
  id: string;
  name: string;
  admins: string[]; // Updated to support multiple admins
  members: string[];
};

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
  teams: UserTeam[]; // Updated to store team details
  ownedModels: string[];
};

export default function AccessPage() {
  const { user } = useContext(UserContext);

  // Determine the user role
  let userRole = '';
  let roleDescription = '';

  if (user?.global_admin) {
    userRole = 'Global Admin';
    roleDescription =
      'This role has read and write access to all members, models, and applications.';
  } else if (user?.teams.some((team) => team.role === 'team_admin')) {
    userRole = 'Team Admin';
    roleDescription =
      'This role has read and write access to all team members, models, and applications in the team.';
  } else {
    userRole = 'User'; // Default role if not an admin
    roleDescription = 'This role has limited access based on specific team permissions.';
  }

  // State to manage models, teams, and users
  const [models, setModels] = useState<Model[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [newTeamName, setNewTeamName] = useState<string>('');
  const [newTeamAdmin, setNewTeamAdmin] = useState<string>('');
  const [newTeamMembers, setNewTeamMembers] = useState<string[]>([]);
  const [selectedTeamForAdd, setSelectedTeamForAdd] = useState<string>('');
  const [selectedTeamForRemove, setSelectedTeamForRemove] = useState<string>('');
  const [newMember, setNewMember] = useState<string>('');
  const [memberToRemove, setMemberToRemove] = useState<string>('');

  const getModels = async () => {
    try {
      const response = await fetchAllModels();
      console.log('Fetched Models:', response.data); // Print out the results
      const modelData = response.data.map(
        (model): Model => ({
          name: model.model_name,
          type:
            model.access_level === 'private'
              ? 'Private Model'
              : model.access_level === 'protected'
                ? 'Protected Model'
                : 'Public Model',
          owner: model.username,
          users: [], // To be populated later
          team: model.team_id !== 'None' ? model.team_id : undefined,
          teamAdmin: undefined, // To be populated later
          domain: model.domain,
          latency: model.latency,
          modelId: model.model_id,
          numParams: model.num_params,
          publishDate: model.publish_date,
          size: model.size,
          sizeInMemory: model.size_in_memory,
          subType: model.sub_type,
          thirdaiVersion: model.thirdai_version,
          trainingTime: model.training_time,
        })
      );
      setModels(modelData);
    } catch (error) {
      console.error('Failed to fetch models', error);
      alert('Failed to fetch models' + error);
    }
  };

  const getUsers = async () => {
    try {
      const response = await fetchAllUsers();
      console.log('Fetched Users:', response.data); // Print out the results
      const userData = response.data.map(
        (user): User => ({
          id: user.id,
          name: user.username,
          email: user.email,
          role: user.global_admin ? 'Global Admin' : 'Member', // Adjust the logic if you have Team Admins
          teams: user.teams.map((team) => ({
            id: team.team_id,
            name: team.team_name,
            role: team.role,
          })),
          ownedModels: models
            .filter((model) => model.owner === user.username)
            .map((model) => model.name),
        })
      );
      setUsers(userData);
    } catch (error) {
      console.error('Failed to fetch users', error);
      alert('Failed to fetch users' + error);
    }
  };

  const getTeams = async () => {
    try {
      const response = await fetchAllTeams();
      console.log('Fetched Teams:', response.data); // Print out the results
      const teamData = response.data.map((team): Team => {
        const members: string[] = [];
        const admins: string[] = []; // Collect multiple admins

        // Populate members and admins from users and models data
        users.forEach((user) => {
          const userTeam = user.teams.find((ut) => ut.id === team.id);
          if (userTeam) {
            members.push(user.name);
            if (userTeam.role === 'team_admin') {
              admins.push(user.name); // Add to admins array
            }
          }
        });

        return {
          id: team.id,
          name: team.name,
          admins: admins, // Store the admins array
          members: members,
        };
      });

      setTeams(teamData);
    } catch (error) {
      console.error('Failed to fetch teams', error);
      alert('Failed to fetch teams' + error);
    }
  };

  // Handle model type change
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [selectedType, setSelectedType] = useState<
    'Private Model' | 'Protected Model' | 'Public Model' | null
  >(null);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null); // For team selection

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
        default:
          return;
      }

      // Call the API to update the model access level
      await updateModelAccessLevel(model_identifier, access_level, team_id);

      // Update the models state
      await getModels();
      await getUsers();
      await getTeams();

      // Reset editing state
      setEditingIndex(null);
      setSelectedType(null);
      setSelectedTeam(null);
    } catch (error) {
      console.error('Failed to update model access level', error);
      alert('Failed to update model access level' + error);
    }
  };

  const handleDeleteModel = async (index: number) => {
    const model = models[index];
    const model_identifier = `${model.owner}/${model.name}`;

    try {
      // Confirm deletion with the user
      const isConfirmed = window.confirm(
        `Are you sure you want to delete the model "${model.name}"?`
      );
      if (!isConfirmed) return;

      // Call the API to delete the model
      await deleteModel(model_identifier);

      // Optionally, refresh the models after deletion
      await getModels();
      await getUsers();
      await getTeams();
    } catch (error) {
      console.error('Failed to delete model', error);
      alert('Failed to delete model: ' + error);
    }
  };

  // Create a new team
  const createNewTeam = async () => {
    try {
      // Create the team
      const createdTeam = await createTeam(newTeamName);
      const team_id = createdTeam.data.team_id; // Correctly accessing the team ID

      // Add members to the team
      for (const memberName of newTeamMembers) {
        const member = users.find((user) => user.name === memberName);
        if (member) {
          await addUserToTeam(member.email, team_id);
        } else {
          console.error(`User with name ${memberName} not found`);
          alert(`User with name ${memberName} not found`);
        }
      }

      // Assign the admin to the team
      const admin = users.find((user) => user.name === newTeamAdmin);
      if (admin) {
        await assignTeamAdmin(admin.email, team_id);
      } else {
        console.error(`User with name ${newTeamAdmin} not found`);
        alert(`User with name ${newTeamAdmin} not found`);
      }

      // Update the state
      await getModels();
      await getUsers();
      await getTeams();

      // Clear the input fields
      setNewTeamName('');
      setNewTeamAdmin('');
      setNewTeamMembers([]);
    } catch (error) {
      console.error('Failed to create new team', error);
      alert('Failed to create new team' + error);
    }
  };

  // Add a member to an existing team
  const addMemberToTeam = async () => {
    try {
      // Find the team by name
      const team = teams.find((t) => t.name === selectedTeamForAdd);
      if (!team) {
        console.error('Selected team not found');
        alert('Selected team not found');
        return;
      }

      // Find the user by name
      const user = users.find((u) => u.name === newMember);
      if (!user) {
        console.error('User not found');
        alert('User not found');
        return;
      }

      // Call the function to add the user to the team
      await addUserToTeam(user.email, team.id);

      // Optionally update the team members state (if needed)
      await getModels();
      await getUsers();
      await getTeams();

      setSelectedTeamForAdd(''); // Clear the selected team
      setNewMember(''); // Clear the new member input
    } catch (error) {
      console.error('Failed to add member to team', error);
      alert('Failed to add member to team' + error);
    }
  };

  const removeMemberFromTeam = async () => {
    try {
      // Find the team by name
      const team = teams.find((t) => t.name === selectedTeamForRemove);
      if (!team) {
        console.error('Selected team not found');
        alert('Selected team not found');
        return;
      }

      // Find the user by name
      const user = users.find((u) => u.name === memberToRemove);
      if (!user) {
        console.error('User not found');
        alert('User not found');
        return;
      }

      // Call the function to remove the user from the team
      await deleteUserFromTeam(user.email, team.id);

      // Optionally update the team members state (if needed)
      await getModels();
      await getUsers();
      await getTeams();

      setSelectedTeamForRemove(''); // Clear the selected team
      setMemberToRemove(''); // Clear the member input
    } catch (error) {
      console.error('Failed to remove member from team', error);
      alert('Failed to remove member from team' + error);
    }
  };

  // Delete a team and update protected models
  const deleteTeam = async (teamName: string) => {
    try {
      // Find the team by name
      const team = teams.find((t) => t.name === teamName);
      if (!team) {
        console.error('Team not found');
        alert('Team not found');
        return;
      }

      // Call the API to delete the team
      await deleteTeamById(team.id);

      await getModels();
      await getUsers();
      await getTeams();
    } catch (error) {
      console.error('Failed to delete team', error);
      alert('Failed to delete team' + error);
    }
  };

  // Delete a user account and update owned models
  const deleteUser = async (userName: string) => {
    try {
      // Find the user by name
      const user = users.find((u) => u.name === userName);
      if (!user) {
        console.error('User not found');
        alert('User not found');
        return;
      }

      // Call the API to delete the user
      await deleteUserAccount(user.email);

      // Update the states
      await getModels();
      await getUsers();
      await getTeams();
    } catch (error) {
      console.error('Failed to delete user', error);
      alert('Failed to delete user' + error);
    }
  };

  useEffect(() => {
    getModels();
    getUsers();
  }, []);

  useEffect(() => {
    getTeams();
  }, [users]);

  // State to manage workflows
  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  const getWorkflows = async () => {
    try {
      const fetchedWorkflows = await fetchWorkflows();
      setWorkflows(fetchedWorkflows);
    } catch (error) {
      console.error('Failed to fetch workflows', error);
      alert('Failed to fetch workflows' + error);
    }
  };

  useEffect(() => {
    getWorkflows();
  }, []);

  // Handle team level change
  const [newAdmin, setNewAdmin] = useState('');
  const [adminToRemove, setAdminToRemove] = useState('');
  const [selectedTeamForRemoveAdmin, setSelectedTeamForRemoveAdmin] = useState('');
  const [selectedTeamForAddAdmin, setSelectedTeamForAddAdmin] = useState('');

  const assignAdminToTeam = async () => {
    if (selectedTeamForAddAdmin && newAdmin) {
      // Find the team ID based on the selected team name
      const selectedTeam = teams.find((team) => team.name === selectedTeamForAddAdmin);

      if (!selectedTeam) {
        alert('Selected team not found.');
        return;
      }

      // Find the user email based on the selected admin's name
      const user = users.find((u) => u.name === newAdmin);
      if (!user) {
        alert('User not found.');
        return;
      }

      try {
        // Use the team ID and user email in the API call
        await assignTeamAdmin(user.email, selectedTeam.id);

        // Update state or UI by calling these functions
        await getModels();
        await getUsers();
        await getTeams();
      } catch (error) {
        console.error('Error adding admin:', error);
        alert('Failed to add admin.');
      }
    } else {
      alert('Please select a team and enter an admin name.');
    }
  };

  const removeAdminFromTeam = async () => {
    if (selectedTeamForRemoveAdmin && adminToRemove) {
      // Find the team ID based on the selected team name
      const selectedTeam = teams.find((team) => team.name === selectedTeamForRemoveAdmin);

      if (!selectedTeam) {
        alert('Selected team not found.');
        return;
      }

      // Find the user email based on the admin's name to be removed
      const user = users.find((u) => u.name === adminToRemove);
      if (!user) {
        alert('User not found.');
        return;
      }

      try {
        // Use the team ID and user email in the API call
        await removeTeamAdmin(user.email, selectedTeam.id);

        // Update state or UI by calling these functions
        await getModels();
        await getUsers();
        await getTeams();

        setSelectedTeamForRemoveAdmin(''); // Clear the selected team
        setAdminToRemove(''); // Clear the admin input
      } catch (error) {
        console.error('Error removing admin:', error);
        alert('Failed to remove admin.');
      }
    } else {
      alert('Please select a team and enter the admin name.');
    }
  };

  // For single string values
  const handleSingleChange = (setter: React.Dispatch<React.SetStateAction<string>>) => {
    return (value: string | string[]) => {
      if (typeof value === 'string') {
        setter(value);
      }
    };
  };

  // For multiple string values
  const handleMultipleChange = (setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    return (value: string | string[]) => {
      if (Array.isArray(value)) {
        setter(value);
      }
    };
  };
  const handleSelectedTeamAdd = (team: string) => {
    setSelectedTeamForAdd(team);
    // console.log("Selected Team to add -> ", team.name);
  };
  const handleSelectedTeamRemove = (team: string) => {
    setSelectedTeamForRemove(team);
    // console.log("Selected team to remove -> ", team.name);
  };
  const handleAdminAdd = (team: string) => {
    setSelectedTeamForAddAdmin(team);
  };
  const handleAdminRemove = (team: string) => {
    setSelectedTeamForRemoveAdmin(team);
  };
  // Handle OpenAI key change
  const [apiKey, setApiKey] = useState(''); // Display the masked API key
  const [newApiKey, setNewApiKey] = useState(''); // For storing the new API key
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    // Fetch the existing OpenAI API key (masked)
    async function fetchApiKey() {
      const response = await fetch('/endpoints/get_openai_key');
      const data = await response.json();
      if (data.apiKey) {
        setApiKey(data.apiKey); // set masked API key
      }
    }

    fetchApiKey();
  }, []);

  const handleSave = async () => {
    if (!newApiKey) {
      alert('Please enter a new OpenAI API Key');
      return;
    }

    setLoading(true);

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

    setLoading(false);
  };

  return (
    <div className="max-w-7xl mx-auto p-6 bg-gray-50 min-h-screen">
      <Card className="shadow-lg">
        <CardHeader className="bg-blue-500 text-white p-6 rounded-t-lg">
          <CardTitle className="text-2xl font-bold">Manage Access</CardTitle>
          <CardDescription className="text-white">
            View all personnel and their access.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6 bg-white rounded-b-lg">
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-800">{userRole}</h2>
            <p className="text-gray-600">{roleDescription}</p>
          </div>

          {/* Models Section */}
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
                          <div>
                            Team: {teams.find((team) => team.id === model.team)?.name || 'None'}
                          </div>
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
                                e.target.value as
                                  | 'Private Model'
                                  | 'Protected Model'
                                  | 'Public Model'
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
                        <Button onClick={() => setEditingIndex(index)} variant="contained">
                          Change Access
                        </Button>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      <Button
                        onClick={() => handleDeleteModel(index)}
                        color="error"
                        variant="contained"
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Workflows Section */}
          <div className="mb-12">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">Workflows</h3>
            <table className="w-full bg-white rounded-lg shadow-md overflow-hidden">
              <thead className="bg-gray-100">
                <tr>
                  <th className="py-3 px-4 text-left text-gray-700">Workflow Name</th>
                  <th className="py-3 px-4 text-left text-gray-700">Type</th>
                  <th className="py-3 px-4 text-left text-gray-700">Status</th>
                  <th className="py-3 px-4 text-left text-gray-700">Created By</th>
                  <th className="py-3 px-4 text-left text-gray-700">Models</th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((workflow, index) => (
                  <tr key={index} className="border-t">
                    <td className="py-3 px-4 text-gray-800">{workflow.name}</td>
                    <td className="py-3 px-4 text-gray-800">{workflow.type}</td>
                    <td className="py-3 px-4 text-gray-800">{workflow.status}</td>
                    <td className="py-3 px-4 text-gray-800">
                      <div>Username: {workflow.created_by.username}</div>
                      <div>Email: {workflow.created_by.email}</div>
                    </td>
                    <td className="py-3 px-4 text-gray-800">
                      {workflow.models.length > 0 ? (
                        workflow.models.map((model, i) => (
                          <div key={i} className="mb-2">
                            <div>Model Name: {model.model_name}</div>
                            <div>Type: {model.type}</div>
                            <div>Published On: {model.publish_date}</div>
                          </div>
                        ))
                      ) : (
                        <div>No models associated with this workflow</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Teams Section */}
          <div className="mb-12">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">Teams</h3>
            {teams.map((team, index) => (
              <div key={index} className="bg-gray-100 p-4 rounded-lg shadow-md mb-8">
                <h4 className="text-lg font-semibold text-gray-800">{team.name}</h4>
                <div className="text-gray-700 mb-2">
                  <span className="font-semibold">Admins:</span> {team.admins.join(', ')}
                </div>
                <div className="text-gray-700 mb-2">
                  <span className="font-semibold">Members:</span> {team.members.join(', ')}
                </div>
                <div className="text-gray-700">
                  <h5 className="text-md font-semibold text-gray-800">Protected Models</h5>
                  <ul className="list-disc pl-5">
                    {models
                      .filter(
                        (model) => model.type === 'Protected Model' && model.team === team.name
                      )
                      .map((model, modelIndex) => (
                        <li key={modelIndex}>{model.name}</li>
                      ))}
                  </ul>
                </div>
                <Button
                  onClick={() => deleteTeam(team.name)}
                  className="mt-4 bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
                >
                  Delete Team
                </Button>
              </div>
            ))}

            {/* Create New Team */}
            <div className="bg-gray-100 p-6 rounded-lg shadow-md mb-8">
              <h4 className="text-lg font-semibold text-gray-800">Create New Team</h4>
              <div className="grid grid-cols-1 gap-4 mt-4">
                <TextField
                  type="text"
                  placeholder="Team Name"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                />
                <AutocompleteInput
                  key={newTeamAdmin} // Use a dynamic key to force re-render
                  value={newTeamAdmin}
                  onChange={handleSingleChange(setNewTeamAdmin)}
                  options={users.map((user) => user.name)}
                  placeholder="Team Admin"
                />
                <AutocompleteInput
                  value={newTeamMembers}
                  onChange={handleMultipleChange(setNewTeamMembers)}
                  options={users.map((user) => user.name)}
                  multiple={true}
                  placeholder="Team Members"
                />
                <Button
                  onClick={() => {
                    if (newTeamAdmin && newTeamMembers.length > 0) {
                      createNewTeam();
                    } else {
                      alert('Please enter both Team Admin and at least one Team Member.');
                    }
                  }}
                  variant="contained"
                >
                  Create Team
                </Button>
              </div>
            </div>

            {/* Add Member to Team */}
            <div className="bg-gray-100 p-6 rounded-lg shadow-md mb-8">
              <h4 className="text-lg font-semibold text-gray-800">Add Member to Team</h4>
              <div className="grid grid-cols-1 gap-4 mt-4">
                <DropdownMenu
                  title="Select Team"
                  handleSelectedTeam={handleSelectedTeamAdd}
                  teams={teams}
                />

                <AutocompleteInput
                  key={selectedTeamForAdd + newMember} // Use a key to force re-render
                  value={newMember}
                  onChange={handleSingleChange(setNewMember)}
                  options={
                    selectedTeamForAdd
                      ? users
                          .map((user) => user.name)
                          .filter(
                            (userName) =>
                              !teams
                                .find((team) => team.name === selectedTeamForAdd)
                                ?.members.includes(userName)
                          )
                      : []
                  }
                  placeholder="New Member"
                />
                <Button onClick={addMemberToTeam} variant="contained" color="success">
                  Add Member
                </Button>
              </div>
            </div>

            {/* Remove Member from Team */}
            <div className="bg-gray-100 p-6 rounded-lg shadow-md mb-8">
              <h4 className="text-lg font-semibold text-gray-800">Remove Member from Team</h4>
              <div className="grid grid-cols-1 gap-4 mt-4">
                <DropdownMenu
                  title="Select Team"
                  handleSelectedTeam={handleSelectedTeamRemove}
                  teams={teams}
                />

                <AutocompleteInput
                  key={selectedTeamForRemove + memberToRemove} // Use a dynamic key to force re-render
                  value={memberToRemove}
                  onChange={handleSingleChange(setMemberToRemove)}
                  options={
                    selectedTeamForRemove
                      ? teams.find((team) => team.name === selectedTeamForRemove)?.members || []
                      : []
                  }
                  placeholder="Member to Remove"
                />
                <Button onClick={removeMemberFromTeam} variant="contained" color="error">
                  Remove Member
                </Button>
              </div>
            </div>

            {/* Add Admin to Team */}
            <div className="bg-gray-100 p-6 rounded-lg shadow-md mb-8">
              <h4 className="text-lg font-semibold text-gray-800">Add Admin to Team</h4>
              <div className="grid grid-cols-1 gap-4 mt-4">
                <DropdownMenu
                  title="Select Team"
                  handleSelectedTeam={handleAdminAdd}
                  teams={teams}
                />

                <AutocompleteInput
                  key={selectedTeamForAddAdmin + newAdmin} // Use a dynamic key to force re-render
                  value={newAdmin}
                  onChange={handleSingleChange(setNewAdmin)}
                  options={users.map((user) => user.name)}
                  placeholder="New Admin"
                />
                <Button onClick={assignAdminToTeam} variant="contained" color="success">
                  Add Admin
                </Button>
              </div>
            </div>

            {/* Remove Admin from Team */}
            <div className="bg-gray-100 p-6 rounded-lg shadow-md mb-8">
              <h4 className="text-lg font-semibold text-gray-800">Remove Admin from Team</h4>
              <div className="grid grid-cols-1 gap-4 mt-4">
                <DropdownMenu
                  title="Select Team"
                  handleSelectedTeam={handleAdminRemove}
                  teams={teams}
                />

                <AutocompleteInput
                  key={selectedTeamForRemoveAdmin + adminToRemove} // Use a dynamic key to force re-render
                  value={adminToRemove}
                  onChange={handleSingleChange(setAdminToRemove)}
                  options={
                    selectedTeamForRemoveAdmin
                      ? teams.find((team) => team.name === selectedTeamForRemoveAdmin)?.members ||
                        []
                      : []
                  }
                  placeholder="Admin to Remove"
                />
                <Button onClick={removeAdminFromTeam} variant="contained" color="error">
                  Remove Admin
                </Button>
              </div>
            </div>
          </div>

          {/* Users Section */}
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

          {/* OpenAI key Section */}
          <div className="bg-gray-100 p-6 rounded-lg shadow-md mb-8">
            <h4 className="text-lg font-semibold text-gray-800">Change OpenAI API Key</h4>
            <div className="mt-4">
              <label className="block text-gray-700">
                Current Organization OpenAI API Key (masked):
              </label>
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
              className={`${loading ? 'cursor-not-allowed' : ''}`}
              disabled={loading}
            >
              {loading ? 'Saving...' : 'Save'}
            </Button>
            {successMessage && <p className="text-green-500 mt-4">{successMessage}</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
