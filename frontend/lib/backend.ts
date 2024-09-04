// /lib/backend.js

import axios from 'axios';
import { access } from 'fs';
import _ from 'lodash';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

export const thirdaiPlatformBaseUrl = _.trim(process.env.NEXT_PUBLIC_THIRDAI_PLATFORM_BASE_URL!, '/');
export const deploymentBaseUrl = _.trim(process.env.NEXT_PUBLIC_DEPLOYMENT_BASE_URL!, '/');

export function getAccessToken(throwIfNotFound: boolean = true): string | null {
  const accessToken = localStorage.getItem('accessToken');
  if (!accessToken && throwIfNotFound) {
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
    const response = await axios.get(`${thirdaiPlatformBaseUrl}/api/model/list`, {
      params: { name },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching private models:', error);
    // alert('Error fetching private models:' + error)
    throw new Error('Failed to fetch private models');
  }
}

export async function fetchPublicModels(name: string) {
  const response = await fetch(`${thirdaiPlatformBaseUrl}/api/model/public-list?name=${name}`);
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
    const response = await axios.get(`${thirdaiPlatformBaseUrl}/api/model/pending-train-models`);
    return response.data;
  } catch (error) {
    console.error('Error fetching private models:', error);
    // alert('Error fetching private models:' + error)
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
    const response = await axios.get<ApiResponse>(`${thirdaiPlatformBaseUrl}/api/deploy/list-deployments`, {
      params: { deployment_id },
    });
    return response.data.data;
  } catch (error) {
      console.error('Error listing deployments:', error);
      alert('Error listing deployments:' + error)
      throw new Error('Failed to list deployments');
  }
}

interface StatusResponse {
  data: {
    model_id: string;
    deploy_status: string;
  };
}

export function getDeployStatus(values: { deployment_identifier: string, model_identifier: string }): Promise<StatusResponse> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(`${thirdaiPlatformBaseUrl}/api/deploy/status?deployment_identifier=${encodeURIComponent(values.deployment_identifier)}&model_identifier=${encodeURIComponent(values.model_identifier)}`)
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

export function stopDeploy(values: { deployment_identifier: string, model_identifier: string }): Promise<StopResponse> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/deploy/stop?deployment_identifier=${encodeURIComponent(values.deployment_identifier)}&model_identifier=${encodeURIComponent(values.model_identifier)}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

interface DeploymentData {
  model_id: string;
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
      .post(`${thirdaiPlatformBaseUrl}/api/deploy/run?${params.toString()}`)
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
      .post(`${thirdaiPlatformBaseUrl}/api/train/ndb?model_name=${name}`, formData)
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

interface CreateWorkflowParams {
  name: string;
  typeName: string;
}

export function create_workflow({ name, typeName }: CreateWorkflowParams): Promise<any> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ name, type_name: typeName });


  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/workflow/create?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.detail || 'Failed to create workflow'));
        } else {
          reject(new Error('Failed to create workflow'));
        }
      });
  });
}

interface AddModelsToWorkflowParams {
  workflowId: string;
  modelIdentifiers: string[];
  components: string[];
}

export function add_models_to_workflow({ workflowId, modelIdentifiers, components }: AddModelsToWorkflowParams): Promise<any> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/workflow/add-models`, {
        workflow_id: workflowId,
        model_ids: modelIdentifiers,
        components,
      })
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.detail || 'Failed to add models to workflow'));
        } else {
          reject(new Error('Failed to add models to workflow'));
        }
      });
  });
}

interface SetGenAIProviderParams {
  workflowId: string;
  provider: string;
}

export function set_gen_ai_provider({ workflowId, provider }: SetGenAIProviderParams): Promise<any> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/workflow/set-gen-ai-provider`, {
        workflow_id: workflowId,
        provider,
      })
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.detail || 'Failed to set generation AI provider'));
        } else {
          reject(new Error('Failed to set generation AI provider'));
        }
      });
  });
}



export interface CreatedBy {
  id: string;
  username: string;
  email: string;
}

export interface Workflow {
  id: string;
  name: string;
  type: string;
  status: string;
  publish_date: string;
  created_by: CreatedBy;
  models: WorkflowModel[];
  gen_ai_provider: string;
}

export function fetchWorkflows(): Promise<Workflow[]> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(`${thirdaiPlatformBaseUrl}/api/workflow/list`)
      .then((res) => {
        resolve(res.data.data); // Assuming the data is inside `data` field
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.detail || 'Failed to fetch workflows'));
        } else {
          reject(new Error('Failed to fetch workflows'));
        }
      });
  });
}

interface ValidateWorkflowResponse {
  status: string;
  message: string;
  data: {
    models: { id: string; name: string }[];
  };
}

export function validate_workflow(workflowId: string): Promise<ValidateWorkflowResponse> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ workflow_id: workflowId });

  return new Promise((resolve, reject) => {
    axios
      .post<ValidateWorkflowResponse>(`${thirdaiPlatformBaseUrl}/api/workflow/validate?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.detail || 'Failed to validate workflow'));
        } else {
          reject(new Error('Failed to validate workflow'));
        }
      });
  });
}


interface StartWorkflowResponse {
  status_code: number;
  message: string;
  data: {
    models: { id: string; name: string }[];
  };
}

export function start_workflow(workflowId: string): Promise<StartWorkflowResponse> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ workflow_id: workflowId });

  return new Promise((resolve, reject) => {
    axios
      .post<StartWorkflowResponse>(`${thirdaiPlatformBaseUrl}/api/workflow/start?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.detail || 'Failed to start workflow'));
        } else {
          reject(new Error('Failed to start workflow'));
        }
      });
  });
}

interface StopWorkflowResponse {
  status_code: number;
  message: string;
}

export function stop_workflow(workflowId: string): Promise<StopWorkflowResponse> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/workflow/stop`, null, {
        params: { workflow_id: workflowId },
      })
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.detail || 'Failed to stop workflow'));
        } else {
          reject(new Error('Failed to stop workflow'));
        }
      });
  });
}

interface DeleteWorkflowResponse {
  status_code: number;
  message: string;
}

export async function delete_workflow(workflowId: string): Promise<DeleteWorkflowResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ workflow_id: workflowId });

  return new Promise((resolve, reject) => {
    axios
      .post<DeleteWorkflowResponse>(`${thirdaiPlatformBaseUrl}/api/workflow/delete?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        console.error('Error deleting workflow:', err);
        alert('Error deleting workflow:' + err)
        reject(new Error('Failed to delete workflow'));
      });
  });
}



interface WorkflowModel {
  access_level: string;
  component: string;
  deploy_status: string;
  domain: string;
  latency: string;
  model_id: string;
  model_name: string;
  num_params: string;
  publish_date: string;
  size: string;
  size_in_memory: string;
  sub_type: string;
  team_id: string | null;
  thirdai_version: string;
  training_time: string;
  type: string;
  user_email: string;
  username: string;
}

interface WorkflowDetailsResponse {
  status_code: number;
  message: string;
  data: {
    id: string;
    name: string;
    type: string;
    type_id: string;
    status: string;
    gen_ai_provider: string;
    models: WorkflowModel[];
  };
}


export async function getWorkflowDetails(workflowId: string): Promise<WorkflowDetailsResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ workflow_id: workflowId });

  return new Promise((resolve, reject) => {
    axios
      .get<WorkflowDetailsResponse>(`${thirdaiPlatformBaseUrl}/api/workflow/details?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        console.error('Error fetching workflow details:', err);
        alert('Error fetching workflow details:' + err)
        reject(new Error('Failed to fetch workflow details'));
      });
  });
}


export function userEmailLogin(email: string, password: string, setAccessToken: (token: string) => void): Promise<any> {
  return new Promise((resolve, reject) => {
    axios
      .get(`${thirdaiPlatformBaseUrl}/api/user/email-login`, {
        headers: {
          Authorization: `Basic ${window.btoa(`${email}:${password}`)}`,
        },
      })
      .then((res) => {
        const accessToken = res.data.data.access_token;

        if (accessToken) {
          // Store accessToken into local storage, replacing any existing one.
          localStorage.setItem('accessToken', accessToken);
          setAccessToken(accessToken);
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
      .post(`${thirdaiPlatformBaseUrl}/api/user/email-signup-basic`, {
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

interface TrainTokenClassifierResponse {
  status_code: number;
  message: string;
  data: {
    model_id: string;
    user_id: string;
  };
}


export function trainTokenClassifier(
  modelName: string,
  samples: TokenClassificationSample[],
  tags: string[]
): Promise<TrainTokenClassifierResponse> {
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
      .post(`${thirdaiPlatformBaseUrl}/api/train/udt?model_name=${modelName}`, formData)
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
  console.log(params);
  const workflowId = params.deploymentId as string;
  const [workflowName, setWorkflowName] = useState<string>("");
  const [deploymentUrl, setDeploymentUrl] = useState<string | undefined>();

  console.log("PARAMS", params);

  useEffect(() => {
    const init = async () => {
      const accessToken = getAccessToken();
      axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

      const params = new URLSearchParams({ workflow_id: workflowId });

      axios
        .get<WorkflowDetailsResponse>(`${thirdaiPlatformBaseUrl}/api/workflow/details?${params.toString()}`)
        .then((res) => {
          setWorkflowName(res.data.data.name)
          for (const model of res.data.data.models) {
            if (model.component === 'nlp') {
              setDeploymentUrl(`${deploymentBaseUrl}/${model.model_id}`);
            }
          }
          })
          .catch((err) => {
            console.error('Error fetching workflow details:', err);
            alert('Error fetching workflow details:' + err)
          });
    };
    init();
  }, []);

  const predict = async (query: string): Promise<TokenClassificationResult> => {
    // Set the default authorization header for axios
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    try {
      const response = await axios.post(`${deploymentUrl}/predict`, {
        query, top_k: 1
      });
      return response.data.data;
    } catch (error) {
      console.error('Error predicting tokens:', error);
      alert('Error predicting tokens:' + error)
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

  const getStats = deploymentUrl && (async (): Promise<DeploymentStats> => {
    axios.defaults.headers.common.Authorization = `Bearer ${getAccessToken()}`;
    try {
      console.log(deploymentUrl);
      const response = await axios.get(`${deploymentUrl}/stats`);
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
      alert("Error fetching stats:" + error)
      throw new Error("Error fetching stats.");
    }
  });

  return {
    workflowName,
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
      .get(`${thirdaiPlatformBaseUrl}/api/model/all-models`)
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
      .get(`${thirdaiPlatformBaseUrl}/api/team/list`)
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
      .get(`${thirdaiPlatformBaseUrl}/api/user/all-users`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}


// MODEL //

export async function updateModelAccessLevel(model_identifier: string, access_level: 'private' | 'protected' | 'public', team_id?: string): Promise<void> {
  const accessToken = getAccessToken(); // Ensure this function is implemented elsewhere in your codebase

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ model_identifier, access_level });

  if (access_level === 'protected' && team_id) {
    params.append('team_id', team_id);
  }

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/model/update-access-level?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error updating model access level:', err);
        alert('Error updating model access level:' + err)
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
      .post(`${thirdaiPlatformBaseUrl}/api/team/create-team?${params.toString()}`)
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
      .post(`${thirdaiPlatformBaseUrl}/api/team/add-user-to-team?${params.toString()}`)
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
      .post(`${thirdaiPlatformBaseUrl}/api/team/assign-team-admin?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export async function removeTeamAdmin(email: string, team_id: string) {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ email, team_id });

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/team/remove-team-admin?${params.toString()}`)
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
      .post(`${thirdaiPlatformBaseUrl}/api/team/remove-user-from-team?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error removing user from team:', err);
        alert('Error removing user from team:' + err)
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
      .delete(`${thirdaiPlatformBaseUrl}/api/team/delete-team?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error deleting team:', err);
        alert('Error deleting team:' + err)
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
      .delete(`${thirdaiPlatformBaseUrl}/api/user/delete-user`, {
        data: { email },
      })
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error deleting user:', err);
        alert('Error deleting user:' + err)
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
      .post(`${thirdaiPlatformBaseUrl}/api/model/update-model?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error updating model:', err);
        alert('Error updating model:' + err)
        reject(err);
      });
  });
}

export interface Team {
  team_id: string;
  team_name: string;
  role: "user" | "team_admin" | "global_admin";
};

export interface User {
  id: string;
  username: string;
  email: string;
  global_admin: boolean;
  teams: Team[];
}

export async function accessTokenUser(accessToken: string | null) {
  if (accessToken === null) {
    return null;
  }

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  try {
    const response = await axios.get(`${thirdaiPlatformBaseUrl}/api/user/info`);
    return response.data.data as User;
  } catch (error) {
    return null;
  }
}



export async function fetchAutoCompleteQueries(modelId: string, query: string) {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ model_id: modelId, query });
  
  try {
    const response = await axios.get(`${deploymentBaseUrl}/cache/suggestions?${params.toString()}`);

    return response.data; // Assuming the backend returns the data directly
  } catch (err) {
    console.error('Error fetching autocomplete suggestions:', err);
    throw err; // Re-throwing the error to handle it in the component
  }
}

export async function fetchCachedGeneration(modelId: string, query: string) {
  const accessToken = getAccessToken();
  axios.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ model_id: modelId, query });

  try {
      const response = await axios.get(`${deploymentBaseUrl}/cache/query?${params.toString()}`);
      return response.data.cached_response; // Assuming the backend returns the data directly
  } catch (err) {
      console.error('Error fetching cached generation:', err);
      throw err; // Re-throwing the error to handle it in the component
  }
}

export async function temporaryCacheToken(modelId: string) {
  const accessToken = getAccessToken();
  axios.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

  const params = new URLSearchParams({model_id: modelId});

  try {
      const response = await axios.get(`${deploymentBaseUrl}/cache/token?${params.toString()}`);
      return response.data; // Assuming the backend returns the data directly
  } catch (err) {
      console.error('Error getting temporary cache access token:', err);
      throw err; // Re-throwing the error to handle it in the component
  }
}
