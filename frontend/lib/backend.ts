// /lib/backend.js

import axios from 'axios';
import _ from 'lodash';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

export const thirdaiPlatformBaseUrl = _.trim(process.env.THIRDAI_PLATFORM_BASE_URL!, '/');
export const deploymentBaseUrl = _.trim(process.env.DEPLOYMENT_BASE_URL!, '/');

export function getAccessToken(): string {
  const accessToken = localStorage.getItem('accessToken');
  if (!accessToken) {
    throw new Error('Access token is not available');
  }
  return accessToken;
}

export function getUsername(): string {
  const username = localStorage.getItem('username');
  if (!username) {
    throw new Error('Username is not available');
  }
  return username;
}

export async function fetchPrivateModels(name: string) {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  try {
    const response = await axios.get(`http://localhost:8000/api/model/list`, {
      params: { name },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching private models:', error);
    throw new Error('Failed to fetch private models');
  }
}

export async function fetchPublicModels(name: string) {
    const response = await fetch(`http://localhost:8000/api/model/public-list?name=${name}`);
    if (!response.ok) {
        throw new Error('Failed to fetch public models');
    }
    return response.json();
}

// Define a type for the pending model data structure
type PendingModel = {
  model_name: string;
  status: string;
  username: string;
};

export async function fetchPendingModels(): Promise<PendingModel> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  try {
    const response = await axios.get(`http://localhost:8000/api/model/pending-train-models`);
    return response.data;
  } catch (error) {
    console.error('Error fetching private models:', error);
    throw new Error('Failed to fetch private models');
  }
}


export interface Deployment {
  name: string;
  deployment_username: string;
  model_name: string;
  model_username: string;
  status: string;
  metadata: any;
  modelID: string;
}

export interface ApiResponse {
  status_code: number;
  message: string;
  data: Deployment[];
}

export async function listDeployments(deployment_id: string): Promise<Deployment[]> {
  const accessToken = getAccessToken(); // Ensure this function is implemented to get the access token
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  try {
      const response = await axios.get<ApiResponse>('http://localhost:8000/api/deploy/list-deployments', {
          params: { deployment_id },
      });
      return response.data.data;
  } catch (error) {
      console.error('Error listing deployments:', error);
      throw new Error('Failed to list deployments');
  }
}

interface StatusResponse {
  data: {
    deployment_id: string;
    status: string;
  };
}

export function getDeployStatus(values: { deployment_identifier: string }): Promise<StatusResponse> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(`http://localhost:8000/api/deploy/status?deployment_identifier=${encodeURIComponent(values.deployment_identifier)}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

interface StopResponse {
  data: {
    deployment_id: string;
  };
  status: string;
}

export function stopDeploy(values: { deployment_identifier: string }): Promise<StopResponse> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/deploy/stop?deployment_identifier=${encodeURIComponent(values.deployment_identifier)}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

interface DeploymentData {
  deployment_id: string;
  deployment_name: string;
  model_identifier: string;
  status: string;
}

interface DeploymentResponse {
  data: DeploymentData;
  message: string;
  status: string;
}

export function deployModel(values: { deployment_name: string; model_identifier: string, use_llm_guardrail?: boolean, token_model_identifier?: string;
 }) : 
  Promise<DeploymentResponse>  {
  
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  let params;

  if (values.token_model_identifier) {
    params = new URLSearchParams({
      deployment_name: values.deployment_name,
      model_identifier: values.model_identifier,
      use_llm_guardrail: values.use_llm_guardrail ? 'true' : 'false',
      token_model_identifier: values.token_model_identifier
    }); 
  } else {
    params = new URLSearchParams({
      deployment_name: values.deployment_name,
      model_identifier: values.model_identifier,
      use_llm_guardrail: values.use_llm_guardrail ? 'true' : 'false'
    }); 
  }

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/deploy/run?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

interface TrainNdbParams {
    name: string;
    formData: FormData;
}

export function train_ndb({ name, formData }: TrainNdbParams): Promise<any> {
    // Retrieve the access token from local storage
    const accessToken = getAccessToken()

    // Set the default authorization header for axios
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

    return new Promise((resolve, reject) => {
        axios
            .post(`http://localhost:8000/api/train/ndb?model_name=${name}`, formData)
            .then((res) => {
                resolve(res.data);
            })
            .catch((err) => {
                if (err.response && err.response.data) {
                    reject(new Error(err.response.data.detail || 'Failed to run model'));
                } else {
                    reject(new Error('Failed to run model'));
                }
            });
    });
}

// Define the interface for the expected response
interface RagEntryResponse {
  // Define the structure of your response here
  success: boolean;
  message: string;
  data?: any;
}

// Define the interface for the input values
export interface RagEntryValues {
  model_name: string;
  ndb_model_id?: string;
  use_llm_guardrail?: boolean;
  token_model_id?: string;
}

export function addRagEntry(values: RagEntryValues): Promise<RagEntryResponse> {
  const accessToken = getAccessToken(); // Make sure you have a function to get the access token

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  // Prepare the query parameters
  const params = new URLSearchParams();
  params.append('model_name', values.model_name);
  if (values.ndb_model_id) {
    params.append('ndb_model_id', values.ndb_model_id);
  }
  if (values.use_llm_guardrail !== undefined) {
    params.append('use_llm_guardrail', values.use_llm_guardrail.toString());
  }
  if (values.token_model_id) {
    params.append('token_model_id', values.token_model_id);
  }

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/model/rag-entry?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}


export function userEmailLogin(email: string, password: string): Promise<any> {
    return new Promise((resolve, reject) => {
      axios
        .get('http://localhost:8000/api/user/email-login', {
          headers: {
            Authorization: `Basic ${window.btoa(`${email}:${password}`)}`,
          },
        })
        .then((res) => {
          const accessToken = res.data.data.access_token;

          if (accessToken) {
            // Store accessToken into local storage, replacing any existing one.
            localStorage.setItem('accessToken', accessToken);
          }

          const username = res.data.data.user.username;

          if (username) {
            localStorage.setItem("username", username);
          }

          resolve(res.data);
        })
        .catch((err) => {
          reject(err);
        });
    });
}

export function userRegister(email: string, password: string, username: string) {
    return new Promise((resolve, reject) => {
      axios
        .post('http://localhost:8000/api/user/email-signup-basic', {
          email,
          password,
          username,
        })
        .then((res) => {
          resolve(res.data);
        })
        .catch((err) => {
          reject(err);
        });
    });
}

interface TokenClassificationSample {
  nerData: string[];
  sentence: string;
}

function samplesToFile(samples: TokenClassificationSample[], sourceColumn: string, targetColumn: string) {
  const rows: string[] = [`${sourceColumn},${targetColumn}`];
  for (const { nerData, sentence } of samples) {
    rows.push('"' + sentence.replace('"', '""') + '",' + nerData.join(' '));
  }
  const csvContent = rows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv" });
  return new File([blob], "data.csv", { type: "text/csv" });
}

export function trainTokenClassifier(modelName: string, samples: TokenClassificationSample[], tags: string[]) {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const sourceColumn = "source";
  const targetColumn = "target";

  const formData = new FormData();
  formData.append("files", samplesToFile(samples, sourceColumn, targetColumn));
  formData.append("files_details_list", JSON.stringify({
    file_details: [{ mode: 'supervised', location: 'local', is_folder: false }]
  }));
  formData.append("extra_options_form", JSON.stringify({
    sub_type: "token",
    source_column: sourceColumn, 
    target_column: targetColumn,
    target_labels: tags,
  }))

  return new Promise((resolve, reject) => {
      axios
          .post(`http://localhost:8000/api/train/udt?model_name=${modelName}`, formData)
          .then((res) => {
              resolve(res.data);
          })
          .catch((err) => {
              if (err.response && err.response.data) {
                  reject(new Error(err.response.data.detail || 'Failed to run model'));
              } else {
                  reject(new Error('Failed to run model'));
              }
          });
  });
};

function useAccessToken() {
  const [accessToken, setAccessToken] = useState<string | undefined>();
  useEffect(() => {
    const accessToken = localStorage.getItem('accessToken');
    if (!accessToken) {
      throw new Error('Access token is not available');
    }
    setAccessToken(accessToken);
  }, []);

  return accessToken;
}

export interface TokenClassificationResult {
  query_text: string;
  tokens: string[],
  predicted_tags: string[][];
}

export function useTokenClassificationEndpoints() {
  const accessToken = useAccessToken();
  const params = useParams();
  const deploymentId = params.deploymentId as string;
  const currentDeploymentBaseUrl = `${deploymentBaseUrl}/${deploymentId}`;
  
  const getName = async (): Promise<string> => {
    // Set the default authorization header for axios
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
  
    try {
      const response = await axios.get(`${thirdaiPlatformBaseUrl}/api/deploy/model-name`, {
        params: { deployment_id: deploymentId },
      });
      return response.data.data.name;
    } catch (error) {
      console.error('Error getting deployment name:', error);
      throw new Error('Failed to get deployment name');
    }
  };

  const predict = async (query: string): Promise<TokenClassificationResult> => {
    // Set the default authorization header for axios
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    try {
      const response = await axios.post(`${currentDeploymentBaseUrl}/predict`, {
        query, top_k: 1
      });
      return response.data.data;
    } catch (error) {
      console.error('Error predicting tokens:', error);
      throw new Error('Failed to predict tokens');
    }
  };

  const formatTime = (timeSeconds: number) => {
    const timeMinutes = Math.floor(timeSeconds / 60);
    const timeHours = Math.floor(timeMinutes / 60);
    const timeDays = Math.floor(timeHours / 24);
    return `${timeDays} days ${timeHours % 24} hours ${timeMinutes % 60} minutes ${timeSeconds % 60} seconds`;
  }

  const formatAmount = (amount: number) => {
    if (amount < 1000) {
      return amount.toString();
    }
    let suffix = "";
    if (amount >= 1000000000) {
      amount /= 1000000000;
      suffix = " B"
    } else if (amount >= 1000000) {
      amount /= 1000000;
      suffix = " M"
    } else {
      amount /= 1000;
      suffix = " K"
    }
    let amountstr = amount.toString();
    if (amountstr.includes(".")) {
      const [wholes, decimals] = amountstr.split(".");
      const decimalsLength = 3 - Math.min(3, wholes.length);
      amountstr = decimalsLength
        ? wholes + "." + decimals.substring(0, decimalsLength)
        : wholes;
    }
    return amountstr + suffix;
  }

  const getStats = async (): Promise<DeploymentStats> => {
    axios.defaults.headers.common.Authorization = `Bearer ${getAccessToken()}`;
    try {
      const response = await axios.get(`${currentDeploymentBaseUrl}/stats`);
      return {
        system: {
          header: ['Name', 'Description'],
          rows: [
            ['CPU', '12 vCPUs'],
            ['CPU Model', 'Intel(R) Xeon(R) CPU E5-2680 v3 @ 2.50GHz'],
            ['Memory', '64 GB RAM'],
            ['System Uptime', formatTime(response.data.data.uptime)],
          ]
        },
        throughput: {
          header: ["Time Period", "Tokens Identified", "Queries Ingested", "Queries Ingested Size"],
          rows: [
            [
              'Past hour',
              formatAmount(response.data.data.past_hour.tokens_identified),
              formatAmount(response.data.data.past_hour.queries_ingested),
              formatAmount(response.data.data.past_hour.queries_ingested_bytes) + "B",
            ],
            [
              'Total',
              formatAmount(response.data.data.total.tokens_identified),
              formatAmount(response.data.data.total.queries_ingested),
              formatAmount(response.data.data.total.queries_ingested_bytes) + "B",
            ],
          ]
        }
      };
    } catch (error) {
      console.error("Error fetching stats:", error);
      throw new Error("Error fetching stats.");
    }
  };
  return {
    getName,
    predict,
    getStats,
  };
}


export interface DeploymentStatsTable {
  header: string[];
  rows: string[][];
}

export interface DeploymentStats {
  system: DeploymentStatsTable;
  throughput: DeploymentStatsTable;
}



//// Admin access dashboard functions /////

// Define the response types for models, teams, and users
interface ModelResponse {
  access_level: string;
  domain: string;
  latency: string;
  model_id: string;
  model_name: string;
  num_params: string;
  publish_date: string;
  size: string;
  size_in_memory: string;
  sub_type: string;
  team_id: string;
  thirdai_version: string;
  training_time: string;
  type: string;
  user_email: string;
  username: string;
}

interface UserTeamInfo {
  team_id: string;
  team_name: string;
  role: 'Member' | 'team_admin' | 'Global Admin';
}

interface UserResponse {
  email: string;
  global_admin: boolean;
  id: string;
  teams: UserTeamInfo[];
  username: string;
}

interface TeamResponse {
  id: string;
  name: string;
}

export async function fetchAllModels(): Promise<{ data: ModelResponse[] }> {
  const accessToken = getAccessToken(); // Make sure this function is implemented elsewhere in your codebase

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get('http://localhost:8000/api/model/all-models')
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export async function fetchAllTeams(): Promise<{ data: TeamResponse[] }> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get('http://localhost:8000/api/team/list')
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export async function fetchAllUsers(): Promise<{ data: UserResponse[] }> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get('http://localhost:8000/api/user/all-users')
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}


// MODEL //

export async function updateModelAccessLevel(model_identifier: string, access_level: 'private' | 'protected' | 'public'): Promise<void> {
  const accessToken = getAccessToken(); // Ensure this function is implemented elsewhere in your codebase

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ model_identifier, access_level });

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/model/update-access-level?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error updating model access level:', err);
        reject(err);
      });
  });
}

// TEAM //

interface CreateTeamResponse {
  status_code: number;
  message: string;
  data: {
    team_id: string;
    team_name: string;
  };
}

export async function createTeam(name: string): Promise<CreateTeamResponse> {
  const accessToken = getAccessToken(); // Make sure this function is implemented elsewhere in your codebase

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ name });

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/team/create-team?${params.toString()}`)
      .then((res) => {
        resolve(res.data as CreateTeamResponse);
      })
      .catch((err) => {
        reject(err);
      });
  });
}



export async function addUserToTeam(email: string, team_id: string, role: string = 'user') {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ email, team_id, role });

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/team/add-user-to-team?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export async function assignTeamAdmin(email: string, team_id: string) {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ email, team_id });

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/team/assign-team-admin?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}


export async function deleteUserFromTeam(email: string, team_id: string): Promise<void> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ email, team_id });

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/team/remove-user-from-team?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error removing user from team:', err);
        reject(err);
      });
  });
}

export async function deleteTeamById(team_id: string): Promise<void> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ team_id });

  return new Promise((resolve, reject) => {
    axios
      .delete(`http://localhost:8000/api/team/delete-team?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error deleting team:', err);
        reject(err);
      });
  });
}


// USER //

export async function deleteUserAccount(email: string): Promise<void> {
  const accessToken = getAccessToken(); // Ensure this function is implemented elsewhere in your codebase

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .delete('http://localhost:8000/api/user/delete-user', {
        data: { email },
      })
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error deleting user:', err);
        reject(err);
      });
  });
}

export async function updateModel(modelIdentifier: string): Promise<void> {
  const accessToken = getAccessToken(); // Ensure this function is implemented elsewhere in your codebase

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ model_identifier: modelIdentifier });

  return new Promise((resolve, reject) => {
    axios
      .post(`http://localhost:8000/api/model/update-model?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error updating model:', err);
        reject(err);
      });
  });
}
