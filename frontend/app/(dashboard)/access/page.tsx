'use client'

import { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';

// Define types for the models, teams, and users
type Model = {
  name: string;
  type: 'Private Model' | 'Protected Model' | 'Public Model';
  owner: string;
  users?: string[];
  team?: string;
  teamAdmin?: string;
};

type Team = {
  name: string;
  admin: string;
  members: string[];
};

type User = {
  name: string;
  role: 'Member' | 'Team Admin' | 'Global Admin';
  adminTeams: string[];
  ownedModels: string[];
};

export default function AccessPage() {
  const userRole = "Global Admin";
  const roleDescription = "This role has read and write access to all team members and models.";

  // Initial data for the models
  const initialModels: Model[] = [
    { name: 'Model A', type: 'Private Model', owner: 'Alice', users: ['Bob', 'Charlie'] },
    { name: 'Model B', type: 'Protected Model', owner: 'Alice', team: 'Team A', teamAdmin: 'Charlie' },
    { name: 'Model C', type: 'Public Model', owner: 'Bob' },
  ];

  // Sample data for the teams
  const initialTeams: Team[] = [
    { name: 'Team A', admin: 'Charlie', members: ['Alice', 'Bob', 'Charlie'] },
    { name: 'Team B', admin: 'Dave', members: ['Eve', 'Frank', 'Grace'] },
  ];

  // Sample data for the users
  const initialUsers: User[] = [
    { name: 'Alice', role: 'Member', adminTeams: [], ownedModels: ['Model A', 'Model B'] },
    { name: 'Bob', role: 'Member', adminTeams: [], ownedModels: ['Model C'] },
    { name: 'Charlie', role: 'Team Admin', adminTeams: ['Team A'], ownedModels: [] },
    { name: 'Dave', role: 'Team Admin', adminTeams: ['Team B'], ownedModels: [] },
    { name: 'Eve', role: 'Member', adminTeams: [], ownedModels: [] },
    { name: 'Frank', role: 'Member', adminTeams: [], ownedModels: [] },
    { name: 'Grace', role: 'Member', adminTeams: [], ownedModels: [] },
    { name: 'Global Admin', role: 'Global Admin', adminTeams: [], ownedModels: [] }
  ];

  // State to manage models, teams, and users
  const [models, setModels] = useState<Model[]>(initialModels);
  const [teams, setTeams] = useState<Team[]>(initialTeams);
  const [users, setUsers] = useState<User[]>(initialUsers);
  const [newTeamName, setNewTeamName] = useState<string>('');
  const [newTeamAdmin, setNewTeamAdmin] = useState<string>('');
  const [newTeamMembers, setNewTeamMembers] = useState<string[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [newMember, setNewMember] = useState<string>('');

  // Handle model type change
  const handleModelTypeChange = (index: number, newType: 'Private Model' | 'Protected Model' | 'Public Model') => {
    const updatedModels = models.map((model, i) =>
      i === index ? { ...model, type: newType } : model
    );
    setModels(updatedModels);
  };

  // Create a new team
  const createNewTeam = () => {
    const newTeam: Team = { name: newTeamName, admin: newTeamAdmin, members: newTeamMembers };
    setTeams([...teams, newTeam]);
    setNewTeamName('');
    setNewTeamAdmin('');
    setNewTeamMembers([]);
  };

  // Add a member to an existing team
  const addMemberToTeam = () => {
    const updatedTeams = teams.map(team =>
      team.name === selectedTeam ? { ...team, members: [...team.members, newMember] } : team
    );
    setTeams(updatedTeams);
    setSelectedTeam('');
    setNewMember('');
  };

  // Delete a team and update protected models
  const deleteTeam = (teamName: string) => {
    const teamAdmin = teams.find(team => team.name === teamName)?.admin;
    setTeams(teams.filter(team => team.name !== teamName));
    const updatedModels = models.map(model =>
      model.team === teamName
        ? { ...model, type: 'Private Model', owner: model.owner, team: undefined, teamAdmin: undefined }
        : model
    ) as Model[];
    setModels(updatedModels);
  };

  // Delete a user account and update owned models
  const deleteUser = (userName: string) => {
    const globalAdmin = users.find(user => user.role === 'Global Admin')?.name || 'None';
    const userToDelete = users.find(user => user.name === userName);
    setUsers(users.filter(user => user.name !== userName));
    const updatedModels = models.map(model => {
      if (model.owner === userName) {
        if (model.type === 'Protected Model') {
          const teamAdmin = users.find(user => user.adminTeams.includes(model.team || ''))?.name || globalAdmin;
          return { ...model, owner: teamAdmin, type: 'Private Model' };
        } else {
          return { ...model, owner: globalAdmin, type: 'Private Model' };
        }
      }
      return model;
    }) as Model[];
    setModels(updatedModels);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manage Access</CardTitle>
        <CardDescription>View all personnel and their access.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <h2 className="text-xl font-semibold">{userRole}</h2>
          <p>{roleDescription}</p>
        </div>

        {/* Models Section */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold">Models</h3>
          <table className="min-w-full bg-white mb-8">
            <thead>
              <tr>
                <th className="py-2 px-4 text-left">Model Name</th>
                <th className="py-2 px-4 text-left">Model Type</th>
                <th className="py-2 px-4 text-left">Access Details</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model, index) => (
                <tr key={index} className="border-t">
                  <td className="py-2 px-4">{model.name}</td>
                  <td className="py-2 px-4">
                    <select
                      value={model.type}
                      onChange={(e) => handleModelTypeChange(index, e.target.value as 'Private Model' | 'Protected Model' | 'Public Model')}
                      className="border border-gray-300 rounded px-2 py-1"
                    >
                      <option value="Private Model">Private Model</option>
                      <option value="Protected Model">Protected Model</option>
                      <option value="Public Model">Public Model</option>
                    </select>
                  </td>
                  <td className="py-2 px-4">
                    {model.type === 'Private Model' && (
                      <div>
                        <div>Owner: {model.owner}</div>
                        <div>Users: {model.users?.join(', ') || 'None'}</div>
                      </div>
                    )}
                    {model.type === 'Protected Model' && (
                      <div>
                        <div>Owner: {model.owner}</div>
                        <div>Team: {model.team || 'None'}</div>
                        <div>Team Admin: {model.teamAdmin || 'None'}</div>
                      </div>
                    )}
                    {model.type === 'Public Model' && (
                      <div>
                        <div>Owner: {model.owner}</div>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Teams Section */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold">Teams</h3>
          {teams.map((team, index) => (
            <div key={index} className="mb-8">
              <h4 className="text-md font-semibold">{team.name}</h4>
              <div className="mb-2">Admin: {team.admin}</div>
              <div className="mb-2">Members: {team.members.join(', ')}</div>
              <div>
                <h5 className="text-sm font-semibold">Protected Models</h5>
                <ul className="list-disc pl-5">
                  {models
                    .filter(model => model.type === 'Protected Model' && model.team === team.name)
                    .map((model, modelIndex) => (
                      <li key={modelIndex}>{model.name}</li>
                    ))}
                </ul>
              </div>
              <button
                onClick={() => deleteTeam(team.name)}
                className="mt-2 bg-red-500 text-white px-2 py-1 rounded"
              >
                Delete Team
              </button>
            </div>
          ))}

          {/* Create New Team */}
          <div className="mb-8">
            <h4 className="text-md font-semibold">Create New Team</h4>
            <div className="mb-2">
              <input
                type="text"
                placeholder="Team Name"
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 mb-2"
              />
              <input
                type="text"
                placeholder="Team Admin"
                value={newTeamAdmin}
                onChange={(e) => setNewTeamAdmin(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 mb-2"
              />
              <input
                type="text"
                placeholder="Team Members (comma separated)"
                value={newTeamMembers.join(', ')}
                onChange={(e) => setNewTeamMembers(e.target.value.split(',').map(member => member.trim()))}
                className="border border-gray-300 rounded px-2 py-1 mb-2"
              />
              <button
                onClick={createNewTeam}
                className="bg-blue-500 text-white px-2 py-1 rounded"
              >
                Create Team
              </button>
            </div>
          </div>

          {/* Add Member to Team */}
          <div>
            <h4 className="text-md font-semibold">Add Member to Team</h4>
            <div className="mb-2">
              <select
                value={selectedTeam}
                onChange={(e) => setSelectedTeam(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 mb-2"
              >
                <option value="">Select Team</option>
                {teams.map((team) => (
                  <option key={team.name} value={team.name}>
                    {team.name}
                  </option>
                ))}
              </select>
              <input
                type="text"
                placeholder="New Member"
                value={newMember}
                onChange={(e) => setNewMember(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 mb-2"
              />
              <button
                onClick={addMemberToTeam}
                className="bg-green-500 text-white px-2 py-1 rounded"
              >
                Add Member
              </button>
            </div>
          </div>
        </div>

        {/* Users Section */}
        <div>
          <h3 className="text-lg font-semibold">Users</h3>
          {users.map((user, index) => (
            <div key={index} className="mb-8">
              <h4 className="text-md font-semibold">{user.name}</h4>
              <div className="mb-2">Role: {user.role}</div>
              {user.adminTeams.length > 0 && (
                <div className="mb-2">Admin Teams: {user.adminTeams.join(', ')}</div>
              )}
              {user.ownedModels.length > 0 && (
                <div>Owned Models: {user.ownedModels.join(', ')}</div>
              )}
              <button
                onClick={() => deleteUser(user.name)}
                className="mt-2 bg-red-500 text-white px-2 py-1 rounded"
              >
                Delete User
              </button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
