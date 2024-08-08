'use client'

import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { fetchAllModels, fetchAllTeams, fetchAllUsers, createTeam, addUserToTeam, assignTeamAdmin } from "@/lib/backend";

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
  admin: string;
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
  teams: UserTeam[];  // Updated to store team details
  ownedModels: string[];
};

export default function AccessPage() {
  const userRole = "Global Admin";
  const roleDescription = "This role has read and write access to all team members and models.";

  // State to manage models, teams, and users
  const [models, setModels] = useState<Model[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<User[]>([]);
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
  const createNewTeam = async () => {
    try {
      // Create the team
      const createdTeam = await createTeam(newTeamName);
      const team_id = createdTeam.data.team_id; // Correctly accessing the team ID

      // Add members to the team
      for (const memberName of newTeamMembers) {
        const member = users.find(user => user.name === memberName);
        if (member) {
          await addUserToTeam(member.email, team_id);
        } else {
          console.error(`User with name ${memberName} not found`);
        }
      }

      // Assign the admin to the team
      const admin = users.find(user => user.name === newTeamAdmin);
      if (admin) {
        await assignTeamAdmin(admin.email, team_id);
      } else {
        console.error(`User with name ${newTeamAdmin} not found`);
      }

      // Update the state
      const newTeam: Team = { id: team_id, name: newTeamName, admin: newTeamAdmin, members: newTeamMembers };
      setTeams([...teams, newTeam]);

      // Clear the input fields
      setNewTeamName('');
      setNewTeamAdmin('');
      setNewTeamMembers([]);
    } catch (error) {
      console.error('Failed to create new team', error);
    }
  };

  // Add a member to an existing team
  const addMemberToTeam = async () => {
    try {
      // Find the team by name
      const team = teams.find(t => t.name === selectedTeam);
      if (!team) {
        console.error('Selected team not found');
        return;
      }

      // Find the user by name
      const user = users.find(u => u.name === newMember);
      if (!user) {
        console.error('User not found');
        return;
      }

      // Call the function to add the user to the team
      await addUserToTeam(user.email, team.id);

      // Optionally update the team members state (if needed)
      const updatedTeams = teams.map(t =>
        t.id === team.id ? { ...t, members: [...t.members, user.name] } : t
      );
      setTeams(updatedTeams)
      setSelectedTeam('');  // Clear the selected team
      setNewMember('');     // Clear the new member input
    } catch (error) {
      console.error('Failed to add member to team', error);
    }
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
    // const globalAdmin = users.find(user => user.role === 'Global Admin')?.name || 'None';
    // const userToDelete = users.find(user => user.name === userName);
    // setUsers(users.filter(user => user.name !== userName));
    // const updatedModels = models.map(model => {
    //   if (model.owner === userName) {
    //     if (model.type === 'Protected Model') {
    //       const teamAdmin = users.find(user => user.adminTeams.includes(model.team || ''))?.name || globalAdmin;
    //       return { ...model, owner: teamAdmin, type: 'Private Model' };
    //     } else {
    //       return { ...model, owner: globalAdmin, type: 'Private Model' };
    //     }
    //   }
    //   return model;
    // }) as Model[];
    // setModels(updatedModels);
  };

  useEffect(() => {
    const getModels = async () => {
      try {
        const response = await fetchAllModels();
        console.log('Fetched Models:', response.data);  // Print out the results
        const modelData = response.data.map((model): Model => ({
          name: model.model_name,
          type: model.access_level === 'private' ? 'Private Model' : model.access_level === 'protected' ? 'Protected Model' : 'Public Model',
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
        }));
        setModels(modelData);
      } catch (error) {
        console.error('Failed to fetch models', error);
      }
    };

    const getUsers = async () => {
      try {
        const response = await fetchAllUsers();
        console.log('Fetched Users:', response.data);  // Print out the results
        const userData = response.data.map((user): User => ({
          id: user.id,
          name: user.username,
          email: user.email,
          role: user.global_admin ? 'Global Admin' : 'Member', // Adjust the logic if you have Team Admins
          teams: user.teams.map(team => ({
            id: team.team_id,
            name: team.team_name,
            role: team.role,
          })),
          ownedModels: models.filter(model => model.owner === user.username).map(model => model.name),
        }));
        setUsers(userData);
      } catch (error) {
        console.error('Failed to fetch users', error);
      }
    };

    getModels();
    getUsers()
  }, []);

  useEffect(()=>{
    const getTeams = async () => {
      try {
        const response = await fetchAllTeams();
        console.log('Fetched Teams:', response.data);  // Print out the results
        const teamData = response.data.map((team): Team => {
          const members: string[] = [];
          let admin = '';

          // Populate members and admin from users and models data
          users.forEach(user => {
            const userTeam = user.teams.find(ut => ut.id === team.id);
            if (userTeam) {
              members.push(user.name);
              if (userTeam.role === 'team_admin') {
                admin = user.name;
              }
            }
          });

          return {
            id: team.id,
            name: team.name,
            admin: admin,
            members: members,
          };
        });

        setTeams(teamData);
      } catch (error) {
        console.error('Failed to fetch teams', error);
      }
    };

    getTeams()
  }, [users])


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
              {user.teams.filter(team => team.role === 'team_admin').length > 0 && (
                <div className="mb-2">
                  Admin Teams: {user.teams.filter(team => team.role === 'team_admin').map(team => team.name).join(', ')}
                </div>
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
