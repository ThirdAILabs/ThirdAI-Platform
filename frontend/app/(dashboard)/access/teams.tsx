'use client';
import React, { useState, useEffect } from 'react';
import { Button, TextField } from '@mui/material';
import AutocompleteInput from '@/components/ui/AutocompleteInput';
import {
  fetchAllTeams,
  createTeam,
  addUserToTeam,
  assignTeamAdmin,
  deleteUserFromTeam,
  deleteTeamById,
  removeTeamAdmin,
  fetchAllUsers,
} from '@/lib/backend';
import DropdownMenu from '@/components/ui/dropDownMenu';
type Team = {
  id: string;
  name: string;
  admins: string[];
  members: string[];
};

type User = {
  id: string;
  name: string;
  email: string;
  role: 'Member' | 'Team Admin' | 'Global Admin';
  teams: { id: string; name: string; role: 'Member' | 'team_admin' | 'Global Admin' }[];
};

type Model = {
  name: string;
  type: 'Private Model' | 'Protected Model' | 'Public Model';
  team?: string;
};

export default function Teams() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [models, setModels] = useState<Model[]>([]);

  // State for creating a new team
  const [newTeamName, setNewTeamName] = useState('');
  const [newTeamAdmin, setNewTeamAdmin] = useState('');
  const [newTeamMembers, setNewTeamMembers] = useState<string[]>([]);

  // State for adding/removing members
  const [selectedTeamForAdd, setSelectedTeamForAdd] = useState('');
  const [selectedTeamForRemove, setSelectedTeamForRemove] = useState('');
  const [newMember, setNewMember] = useState('');
  const [memberToRemove, setMemberToRemove] = useState('');

  // State for adding/removing admins
  const [selectedTeamForAddAdmin, setSelectedTeamForAddAdmin] = useState('');
  const [selectedTeamForRemoveAdmin, setSelectedTeamForRemoveAdmin] = useState('');
  const [newAdmin, setNewAdmin] = useState('');
  const [adminToRemove, setAdminToRemove] = useState('');

  //Satate for force-rendering of DropdownMenu
  const [addMemberKey, setAddMemberKey] = useState(0);
  const [removeMemberKey, setRemoveMemberKey] = useState(0);
  const [addAdminKey, setAddAdminKey] = useState(0);
  const [removeAdminKey, setRemoveAdminKey] = useState(0);
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
        })
      );
      setUsers(userData);
    } catch (error) {
      console.error('Failed to fetch users', error);
      alert('Failed to fetch users' + error);
    }
  };

  useEffect(() => {
    getTeams();
  }, [users]);
  const getTeams = async () => {
    try {
      const response = await fetchAllTeams();
      const teamData = response.data.map((team): Team => {
        const members: string[] = [];
        const admins: string[] = [];

        users.forEach((user) => {
          const userTeam = user.teams.find((ut) => ut.id === team.id);
          if (userTeam) {
            members.push(user.name);
            if (userTeam.role === 'team_admin') {
              admins.push(user.name);
            }
          }
        });

        return {
          id: team.id,
          name: team.name,
          admins: admins,
          members: members,
        };
      });

      setTeams(teamData);
    } catch (error) {
      console.error('Failed to fetch teams', error);
      alert('Failed to fetch teams' + error);
    }
  };

  const createNewTeam = async () => {
    try {
      const createdTeam = await createTeam(newTeamName);
      const team_id = createdTeam.data.team_id;

      for (const memberName of newTeamMembers) {
        const member = users.find((user) => user.name === memberName);
        if (member) {
          await addUserToTeam(member.email, team_id);
        } else {
          console.error(`User with name ${memberName} not found`);
          alert(`User with name ${memberName} not found`);
        }
      }

      const admin = users.find((user) => user.name === newTeamAdmin);
      if (admin) {
        await assignTeamAdmin(admin.email, team_id);
      } else {
        console.error(`User with name ${newTeamAdmin} not found`);
        alert(`User with name ${newTeamAdmin} not found`);
      }

      await getTeams();
      await getUsers();
      setNewTeamName('');
      setNewTeamAdmin('');
      setNewTeamMembers([]);
    } catch (error) {
      console.error('Failed to create new team', error);
      alert('Failed to create new team' + error);
    }
  };

  const addMemberToTeam = async () => {
    try {
      const team = teams.find((t) => t.name === selectedTeamForAdd);
      if (!team) {
        console.error('Selected team not found');
        alert('Selected team not found');
        return;
      }

      const user = users.find((u) => u.name === newMember);
      if (!user) {
        console.error('User not found');
        alert('User not found');
        return;
      }

      await addUserToTeam(user.email, team.id);
      await getTeams();
      await getUsers();
      setSelectedTeamForAdd('Select Team');
      setNewMember('');
      setAddMemberKey((prevKey) => prevKey + 1); // Increment key to force re-render
    } catch (error) {
      console.error('Failed to add member to team', error);
      alert('Failed to add member to team' + error);
    }
  };

  const removeMemberFromTeam = async () => {
    try {
      const team = teams.find((t) => t.name === selectedTeamForRemove);
      if (!team) {
        console.error('Selected team not found');
        alert('Selected team not found');
        return;
      }

      const user = users.find((u) => u.name === memberToRemove);
      if (!user) {
        console.error('User not found');
        alert('User not found');
        return;
      }

      await deleteUserFromTeam(user.email, team.id);
      await getTeams();
      await getUsers();
      setSelectedTeamForRemove('Select Team');
      setMemberToRemove('');
      setRemoveMemberKey((prevKey) => prevKey + 1); // Increment key to force re-render
    } catch (error) {
      console.error('Failed to remove member from team', error);
      alert('Failed to remove member from team' + error);
    }
  };

  const deleteTeam = async (teamName: string) => {
    try {
      const team = teams.find((t) => t.name === teamName);
      if (!team) {
        console.error('Team not found');
        alert('Team not found');
        return;
      }

      await deleteTeamById(team.id);
      await getTeams();
    } catch (error) {
      console.error('Failed to delete team', error);
      alert('Failed to delete team' + error);
    }
  };

  const assignAdminToTeam = async () => {
    if (selectedTeamForAddAdmin && newAdmin) {
      const selectedTeam = teams.find((team) => team.name === selectedTeamForAddAdmin);
      if (!selectedTeam) {
        alert('Selected team not found.');
        return;
      }

      const user = users.find((u) => u.name === newAdmin);
      if (!user) {
        alert('User not found.');
        return;
      }

      try {
        await assignTeamAdmin(user.email, selectedTeam.id);
        await getTeams();
        await getUsers();
        setSelectedTeamForAddAdmin('Select Team');
        setNewAdmin('');
        setAddAdminKey((prevKey) => prevKey + 1); // Increment key to force re-render
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
      const selectedTeam = teams.find((team) => team.name === selectedTeamForRemoveAdmin);
      if (!selectedTeam) {
        alert('Selected team not found.');
        return;
      }

      const user = users.find((u) => u.name === adminToRemove);
      if (!user) {
        alert('User not found.');
        return;
      }

      try {
        await removeTeamAdmin(user.email, selectedTeam.id);
        await getTeams();
        await getUsers();
        setSelectedTeamForRemoveAdmin('Select Team');
        setAdminToRemove('');
        setRemoveAdminKey((prevKey) => prevKey + 1); // Increment key to force re-render
      } catch (error) {
        console.error('Error removing admin:', error);
        alert('Failed to remove admin.');
      }
    } else {
      alert('Please select a team and enter the admin name.');
    }
  };

  const handleSingleChange = (setter: React.Dispatch<React.SetStateAction<string>>) => {
    return (value: string | string[]) => {
      if (typeof value === 'string') {
        setter(value);
      }
    };
  };

  const handleMultipleChange = (setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    return (value: string | string[]) => {
      if (Array.isArray(value)) {
        setter(value);
      }
    };
  };

  const handleSelectedTeamAdd = (team: string) => {
    setSelectedTeamForAdd(team);
  };
  const handleSelectedTeamRemove = (team: string) => {
    setSelectedTeamForRemove(team);
  };
  const handleAdminAdd = (team: string) => {
    setSelectedTeamForAddAdmin(team);
  };
  const handleAdminRemove = (team: string) => {
    setSelectedTeamForRemoveAdmin(team);
  };

  return (
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
                .filter((model) => model.type === 'Protected Model' && model.team === team.name)
                .map((model, modelIndex) => (
                  <li key={modelIndex}>{model.name}</li>
                ))}
            </ul>
          </div>
          <Button onClick={() => deleteTeam(team.name)} variant="contained" color="error">
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
            key={addMemberKey}
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
            key={removeMemberKey}
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
            key={addAdminKey}
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
            key={removeAdminKey}
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
                ? teams.find((team) => team.name === selectedTeamForRemoveAdmin)?.members || []
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
  );
}
