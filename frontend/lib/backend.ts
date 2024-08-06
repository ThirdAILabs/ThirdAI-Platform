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
    return setAccessToken(accessToken);
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

  return {
    getName,
    predict
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

export function useDeploymentStats() {
  const accessToken = useAccessToken();
  const params = useParams();
  const deploymentId = params.deploymentId as string;
  const currentDeploymentBaseUrl = `${deploymentBaseUrl}/${deploymentId}`;
  const [pastHourTokens, setPastHourTokens] = useState(_.random(0.2, 0.6));
  const [allTimeTokens, setAllTimeTokens] = useState(_.random(20, 35));

  const getStats = async (): Promise<DeploymentStats> => {
    try {
      // TODO: Build stats endpoint for nomad jobs and use it
      // const response = await axios.get("http://localhost:8001/stats");
      // console.log(response.data);
      // const data = response.data;

      const start = new Date(2024, 7, 3, 12, 54, 12);
      const uptime = (new Date()).getTime() - start.getTime();
      const uptimeSeconds = Math.floor(uptime / 1000);
      const uptimeMinutes = Math.floor(uptimeSeconds / 60);
      const uptimeHours = Math.floor(uptimeMinutes / 60);
      const uptimeDays = Math.floor(uptimeHours / 24);
      const uptimeString = `${uptimeDays} days ${uptimeHours % 24} hours ${uptimeMinutes % 60} minutes ${uptimeSeconds % 60} seconds`;

      const pastHourTokens = _.random(0.2, 0.3);

      const toReturn = {
        system: {
          header: ['Component', 'Description'],
          rows: [
            ['CPU', '12 vCPUs'],
            ['CPU Model', 'Intel(R) Xeon(R) CPU E5-2680 v3 @ 2.50GHz'],
            ['Memory', '64 GB RAM'],
            ['System Uptime', uptimeString],
          ]
        },
        throughput: {
          header: ["Time Period", "Tokens Identified", "Chunks Parsed", "Files Processed"],
          rows: [
            [
              'Past hour',
              (Math.floor(pastHourTokens * 100) / 100).toLocaleString() + "M",
              Math.floor(pastHourTokens / 12 * 1000).toLocaleString() + "K",
              Math.floor(pastHourTokens / 23123 * 1000).toLocaleString() + "MB",
            ],
            [
              'Total',
              (Math.floor(allTimeTokens * 10) / 10).toLocaleString() + "M",
              (Math.floor(allTimeTokens / 12 * 100) / 100).toLocaleString() + "M",
              Math.floor(allTimeTokens / 231 * 1000).toLocaleString() + "MB",
            ],
          ]
        }
      };
      
      setAllTimeTokens(prev => prev + 0.1);

      return toReturn;

    } catch (error) {
      console.error("Error fetching stats:", error);
      throw new Error("Error fetching stats.");
    }
  };

  return { getStats };
};
