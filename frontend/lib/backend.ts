// /lib/backend.js

import axios from 'axios';
import _ from 'lodash';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

function getAccessToken(): string {
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

export async function fetchPendingModel() {
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

interface StatusResponse {
  data: {
    deployment_id: string;
    status: string;
  };
}

export function getDeployStatus(values: { deployment_identifier: string }): Promise<StatusResponse> {
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

export function deployModel(values: { deployment_name: string; model_identifier: string }) : Promise<DeploymentResponse>  {
  
  const accessToken = getAccessToken()

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(
        `http://localhost:8000/api/deploy/run?deployment_name=${values.deployment_name}&model_identifier=${values.model_identifier}`
      )
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
            .post(`http://localhost:8000/api/train/ndb?model_name=${name}&sharded=${false}`, formData)
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

// deploymentIdParam is the dynamic routing parameter name
// E.g. if called in /app/pagename/[deploymentidparamname]/page.tsx,
// deploymentIdParam should be "deploymentidparamname".
function useDeploymentBaseUrl(deploymentIdParam = "deploymentId") {
  const params = useParams();
  let baseUrl = _.trim(process.env.DEPLOYMENT_BASE_URL!, '/');
  baseUrl += '/' + params[deploymentIdParam];
  return baseUrl;
}

export interface TokenClassificationResult {
  query_text: string;
  tokens: string[],
  predicted_tags: string[][];
}

export function useTokenClassificationEndpoints() {
  const accessToken = useAccessToken();
  const baseUrl = useDeploymentBaseUrl();

  const predict = async (query: string): Promise<TokenClassificationResult> => {
    // Set the default authorization header for axios
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

    try {
      const response = await axios.get(`${baseUrl}/predict`, {
        params: { query, top_k: 1 },
      });
      return response.data;
    } catch (error) {
      console.error('Error predicting tokens:', error);
      throw new Error('Failed to predict tokens');
    }
  }

  const getAvailableTags = async (): Promise<string[]> => {
    // TODO: Create backend endpoint + connect.
    return ["NAME", "CREDITCARDNUMBER", "SSN", "PHONENUMBER", "LOCATION"];
  }

  return {
    predict,
    getAvailableTags
  }
}