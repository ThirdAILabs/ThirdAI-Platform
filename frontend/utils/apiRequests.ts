import { fetchAllModels, fetchAllTeams, fetchAllUsers } from '@/lib/backend';
import exp from 'constants';
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
  admins: string[];
  members: string[];
};

type User = {
  id: string;
  name: string;
  email: string;
  role: 'Member' | 'Team Admin' | 'Global Admin';
  teams: { id: string; name: string; role: 'Member' | 'team_admin' | 'Global Admin' }[];
  ownedModels: string[];
  verified: boolean;
};

const getModels = async () => {
  try {
    const response = await fetchAllModels();
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
        users: [],
        team: model.team_id !== 'None' ? model.team_id : undefined,
        teamAdmin: undefined,
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
    return modelData;
  } catch (error) {
    console.error('Failed to fetch models', error);
    alert('Failed to fetch models' + error);
  }
};

const getUsers = async () => {
  try {
    const response = await fetchAllUsers();
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
        ownedModels: [],
        verified: user.verified,
      })
    );
    return userData;
  } catch (error) {
    console.error('Failed to fetch users', error);
    alert('Failed to fetch users' + error);
  }
};

const getTeams = async () => {
  try {
    const users = await getUsers();
    const response = await fetchAllTeams();
    const teamData = response.data.map((team): Team => {
      const members: string[] = [];
      const admins: string[] = [];
      if (users !== undefined)
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
    return teamData;
  } catch (error) {
    console.error('Failed to fetch teams', error);
    alert('Failed to fetch teams' + error);
  }
};

export { getModels, getTeams, getUsers };
export type { Model, Team, User };
