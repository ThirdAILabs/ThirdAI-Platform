// /lib/backend.js

import axios, { AxiosError } from 'axios';
import { access } from 'fs';
import _ from 'lodash';
import { useParams } from 'next/navigation';
import { useEffect, useState, useCallback } from 'react';

export const thirdaiPlatformBaseUrl = typeof window !== 'undefined' ? window.location.origin : '';
export const deploymentBaseUrl = typeof window !== 'undefined' ? window.location.origin : '';

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
    const response = await axios.get<ApiResponse>(
      `${thirdaiPlatformBaseUrl}/api/deploy/list-deployments`,
      {
        params: { deployment_id },
      }
    );
    return response.data.data;
  } catch (error) {
    console.error('Error listing deployments:', error);
    alert('Error listing deployments:' + error);
    throw new Error('Failed to list deployments');
  }
}

// Update the base interface to match the API response structure

interface BaseStatusResponse {
  data: {
    model_identifier: string; // Changed from model_id to model_identifier
    messages: string[];
  };
}

interface BaseDeployStatusResponse {
  data: {
    model_id: string;
    messages: string[];
  };
}

interface DeployStatusResponse extends BaseDeployStatusResponse {
  data: {
    model_id: string;
    messages: string[];
    deploy_status: string;
  };
}

interface TrainStatusResponse extends BaseStatusResponse {
  data: {
    model_identifier: string;
    messages: string[];
    train_status: string;
    warnings: string[];
    errors: string[];
  };
}

export function getDeployStatus(modelIdentifier: string): Promise<DeployStatusResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(
        `${thirdaiPlatformBaseUrl}/api/deploy/status?model_identifier=${encodeURIComponent(modelIdentifier)}`
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export function getTrainingStatus(modelIdentifier: string): Promise<TrainStatusResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(
        `${thirdaiPlatformBaseUrl}/api/train/status?model_identifier=${encodeURIComponent(modelIdentifier)}`
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

interface LogEntry {
  stderr: string;
  stdout: string;
}

interface LogResponse {
  data: LogEntry[]; // Now it's an array of LogEntry objects
}

export function getTrainingLogs(modelIdentifier: string): Promise<LogResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(
        `${thirdaiPlatformBaseUrl}/api/train/logs?model_identifier=${encodeURIComponent(modelIdentifier)}`
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export function getDeploymentLogs(modelIdentifier: string): Promise<LogResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(
        `${thirdaiPlatformBaseUrl}/api/deploy/logs?model_identifier=${encodeURIComponent(modelIdentifier)}`
      )
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

export function stopDeploy(values: {
  deployment_identifier: string;
  model_identifier: string;
}): Promise<StopResponse> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken();

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(
        `${thirdaiPlatformBaseUrl}/api/deploy/stop?deployment_identifier=${encodeURIComponent(values.deployment_identifier)}&model_identifier=${encodeURIComponent(values.model_identifier)}`
      )
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

export function deployModel(values: {
  deployment_name: string;
  model_identifier: string;
  use_llm_guardrail?: boolean;
  token_model_identifier?: string;
}): Promise<DeploymentResponse> {
  const accessToken = getAccessToken();

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  let params;

  if (values.token_model_identifier) {
    params = new URLSearchParams({
      deployment_name: values.deployment_name,
      model_identifier: values.model_identifier,
      use_llm_guardrail: values.use_llm_guardrail ? 'true' : 'false',
      token_model_identifier: values.token_model_identifier,
    });
  } else {
    params = new URLSearchParams({
      deployment_name: values.deployment_name,
      model_identifier: values.model_identifier,
      use_llm_guardrail: values.use_llm_guardrail ? 'true' : 'false',
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
  const accessToken = getAccessToken();

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

// src/interfaces/TrainNdbParams.ts
export interface JobOptions {
  allocation_cores: number;
  allocation_memory: number;
  // Add other JobOptions fields as necessary
}

export interface RetrainNdbParams {
  model_name: string;
  base_model_identifier: string;
  job_options: JobOptions;
}

export function retrain_ndb({
  model_name,
  base_model_identifier,
  job_options,
}: RetrainNdbParams): Promise<any> {
  // Retrieve the access token from local storage or any other storage mechanism
  const accessToken = getAccessToken();

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  // Initialize URLSearchParams with model_name and base_model_identifier
  const params = new URLSearchParams({
    model_name: model_name,
    base_model_identifier: base_model_identifier,
  });

  // Append job_options fields to the URLSearchParams
  Object.entries(job_options).forEach(([key, value]) => {
    params.append(key, value.toString());
  });

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/train/ndb-retrain?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.message || 'Failed to retrain model'));
        } else {
          reject(new Error('Failed to retrain model'));
        }
      });
  });
}

export async function validateDocumentClassificationFolder(files: FileList) {
  const accessToken = getAccessToken();
  const formData = new FormData();

  // Group files by their categories first
  const categoryMap = new Map<string, File[]>();

  Array.from(files).forEach((file) => {
    const pathParts = file.webkitRelativePath.split('/');
    // Change this to use the category folder name (pathParts[1])
    if (pathParts.length >= 3) {
      const category = pathParts[1]; // Changed from pathParts[0] to pathParts[1]
      if (!categoryMap.has(category)) {
        categoryMap.set(category, []);
      }
      categoryMap.get(category)?.push(file);
    }
  });

  // Debug logging
  console.log('Categories being sent to backend:', Array.from(categoryMap.keys()));

  // Add files to FormData maintaining category structure
  categoryMap.forEach((files, category) => {
    files.forEach((file) => {
      // Include the full relative path in the file name
      formData.append('files', file, file.webkitRelativePath);
    });
  });

  // Debug: Log what's being sent
  console.log(
    'Files being sent:',
    Array.from(formData.getAll('files')).map((f) => {
      if (f instanceof File) {
        return f.name;
      }
      return f;
    })
  );

  try {
    const response = await axios.post(
      `${thirdaiPlatformBaseUrl}/api/train/validate-document-classification-folder`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    console.log('Backend validation response:', response.data);
    return response.data;
  } catch (error) {
    console.error('Validation error details:', error);
    if (axios.isAxiosError(error) && error.response?.data) {
      throw new Error(error.response.data.message || 'Failed to validate folder structure');
    }
    throw new Error('Failed to validate folder structure');
  }
}

interface TrainDocumentClassifierParams {
  modelName: string;
  files: FileList;
  testSplit?: number;
  nTargetClasses?: number; // Add this to accept the dynamic number of classes
}

export async function trainDocumentClassifier({
  modelName,
  files,
  testSplit = 0.1,
  nTargetClasses,
}: TrainDocumentClassifierParams): Promise<any> {
  const accessToken = getAccessToken();

  try {
    const formData = new FormData();

    // Add all document files to FormData
    Array.from(files).forEach((file) => {
      formData.append('files', file, file.webkitRelativePath);
    });

    // Prepare file info with webkitRelativePath to preserve directory structure
    const fileInfo = {
      supervised_files: Array.from(files).map((file) => ({
        filename: file.name,
        content_type: file.type,
        path: file.webkitRelativePath,
        location: 'local',
      })),
      test_files: [],
    };
    formData.append('file_info', JSON.stringify(fileInfo));

    // Model options for document classification
    const modelOptions = {
      model_type: 'udt',
      udt_options: {
        udt_sub_type: 'document',
        text_column: 'text',
        label_column: 'label',
        n_target_classes: nTargetClasses, // Use the dynamically passed number of classes
        word_limit: 1000, // Configure word limit
      },
      train_options: {
        test_split: testSplit,
      },
    };
    formData.append('model_options', JSON.stringify(modelOptions));

    // Job options
    const jobOptions = {
      allocation_cores: 2,
      allocation_memory: 16000,
    };
    formData.append('job_options', JSON.stringify(jobOptions));

    // Train the model
    const params = new URLSearchParams({ model_name: modelName });
    const response = await axios.post(
      `${thirdaiPlatformBaseUrl}/api/train/udt?${params.toString()}`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    if (response.data?.status === 'failed') {
      throw new Error(response.data.message || 'Failed to train model');
    }

    return response.data;
  } catch (error) {
    console.error('Training error:', error);
    if (axios.isAxiosError(error) && error.response?.data) {
      throw new Error(
        error.response.data.message || 'Failed to train document classification model'
      );
    }
    throw error instanceof Error
      ? error
      : new Error('Failed to train document classification model');
  }
}

export async function validateSentenceClassifierCSV(file: File) {
  const accessToken = getAccessToken();
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await axios.post(
      `${thirdaiPlatformBaseUrl}/api/train/validate-text-classification-csv`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return {
      valid: response.data.status === 'success',
      message: response.data.message,
      labels: response.data.data?.labels || [],
    };
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const errorMessage = error.response?.data?.message || 'Failed to validate CSV';
      return {
        valid: false,
        message: errorMessage,
        labels: [],
      };
    }
    return {
      valid: false,
      message: 'Failed to validate CSV',
      labels: [],
    };
  }
}

interface TrainTextClassifierParams {
  modelName: string;
  file: File;
  labels: string[];
  testSplit?: number;
}

export function trainTextClassifierWithCSV({
  modelName,
  file,
  labels,
  testSplit = 0.1,
}: TrainTextClassifierParams): Promise<any> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  // Create FormData instance to handle file upload
  const formData = new FormData();
  formData.append('files', file);

  // Add file info with correct location type
  const fileInfo = {
    supervised_files: [
      {
        filename: file.name,
        content_type: file.type,
        path: file.name,
        location: 'local',
      },
    ],
    test_files: [], // No test files for now, will be split from training data
  };
  formData.append('file_info', JSON.stringify(fileInfo));

  // Model options for text classification with TextClassificationOptions
  const modelOptions = {
    model_type: 'udt',
    udt_options: {
      udt_sub_type: 'text',
      text_column: 'text', // Column containing the text
      label_column: 'label', // Column containing the label
      n_target_classes: labels.length, // Number of unique labels
      target_labels: labels, // Array of label names
    },
    train_options: {
      test_split: testSplit,
    },
  };
  formData.append('model_options', JSON.stringify(modelOptions));

  // Job options (using defaults)
  const jobOptions = {
    allocation_cores: 1,
    allocation_memory: 8000,
  };
  formData.append('job_options', JSON.stringify(jobOptions));

  // Create URL with query parameters
  const params = new URLSearchParams({
    model_name: modelName,
    base_model_identifier: '', // Empty string for new model
  });

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/train/udt?${params.toString()}`, formData)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (axios.isAxiosError(err)) {
          const axiosError = err as AxiosError;
          if (axiosError.response && axiosError.response.data) {
            reject(
              new Error(
                (axiosError.response.data as any).detail ||
                  'Failed to train text classification model'
              )
            );
          } else {
            reject(new Error('Failed to train text classification model'));
          }
        } else {
          reject(new Error('Failed to train text classification model'));
        }
      });
  });
}

interface RetrainTokenClassifierParams {
  model_name: string;
  base_model_identifier?: string;
}

export function retrainTokenClassifier({
  model_name,
  base_model_identifier,
}: RetrainTokenClassifierParams): Promise<any> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({
    model_name,
    llm_provider: 'openai',
  });

  if (base_model_identifier) {
    params.append('base_model_identifier', base_model_identifier);
  }

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/train/retrain-udt?${params.toString()}`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (axios.isAxiosError(err)) {
          const axiosError = err as AxiosError;
          if (axiosError.response && axiosError.response.data) {
            reject(
              new Error((axiosError.response.data as any).detail || 'Failed to retrain UDT model')
            );
          } else {
            reject(new Error('Failed to retrain UDT model'));
          }
        } else {
          reject(new Error('Failed to retrain UDT model'));
        }
      });
  });
}

interface trainTokenClassifierWithCSVParams {
  model_name: string;
  file: File;
  labels: string[];
  test_split?: number;
}

export function trainTokenClassifierWithCSV({
  model_name,
  file,
  labels,
  test_split = 0.1,
}: trainTokenClassifierWithCSVParams): Promise<any> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  // Create FormData instance to handle file upload
  const formData = new FormData();
  formData.append('files', file);

  // Add file info with correct location type
  const fileInfo = {
    supervised_files: [
      {
        filename: file.name,
        content_type: file.type,
        path: file.name,
        location: 'local',
      },
    ],
    test_files: [],
  };
  formData.append('file_info', JSON.stringify(fileInfo));

  // Model options for token classification with detected labels
  const modelOptions = {
    model_type: 'udt',
    udt_options: {
      udt_sub_type: 'token',
      source_column: 'source',
      target_column: 'target',
      target_labels: labels,
    },
    train_options: {
      test_split: test_split,
    },
  };
  formData.append('model_options', JSON.stringify(modelOptions));

  // Job options (using defaults)
  const jobOptions = {
    allocation_cores: 1,
    allocation_memory: 8000,
  };
  formData.append('job_options', JSON.stringify(jobOptions));

  // Create URL with query parameters
  const params = new URLSearchParams({
    model_name,
    base_model_identifier: '', // Empty string for new model
  });

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/train/udt?${params.toString()}`, formData)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (axios.isAxiosError(err)) {
          const axiosError = err as AxiosError;
          if (axiosError.response && axiosError.response.data) {
            reject(
              new Error(
                (axiosError.response.data as any).detail ||
                  'Failed to train token classification model'
              )
            );
          } else {
            reject(new Error('Failed to train token classification model'));
          }
        } else {
          reject(new Error('Failed to train token classification model'));
        }
      });
  });
}

interface TrainUDTWithCSVParams {
  model_name: string;
  file: File;
  base_model_identifier: string;
  test_split?: number;
}

export function trainUDTWithCSV({
  model_name,
  file,
  base_model_identifier,
  test_split = 0.1,
}: TrainUDTWithCSVParams): Promise<any> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  // Create FormData instance to handle file upload
  const formData = new FormData();
  formData.append('files', file);

  // Add file info with correct location type
  const fileInfo = {
    supervised_files: [
      {
        filename: file.name,
        content_type: file.type,
        path: file.name,
        location: 'local',
      },
    ],
    test_files: [],
  };
  formData.append('file_info', JSON.stringify(fileInfo));

  // Simplified model options for token classification
  const modelOptions = {
    udt_options: {
      udt_sub_type: 'token',
      source_column: '',
      target_column: '',
      target_labels: [],
    },
    train_options: {
      test_split: test_split,
    },
  };
  formData.append('model_options', JSON.stringify(modelOptions));

  // Create URL with query parameters
  const params = new URLSearchParams({
    model_name,
    base_model_identifier,
  });

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/train/udt?${params.toString()}`, formData)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (axios.isAxiosError(err)) {
          const axiosError = err as AxiosError;
          if (axiosError.response && axiosError.response.data) {
            reject(
              new Error(
                (axiosError.response.data as any).detail || 'Failed to train UDT model with CSV'
              )
            );
          } else {
            reject(new Error('Failed to train UDT model with CSV'));
          }
        } else {
          reject(new Error('Failed to train UDT model with CSV'));
        }
      });
  });
}

interface APIResponse {
  status: string;
  message: string;
  data?: {
    valid: boolean;
    labels?: string[];
  };
}

interface ValidationResult {
  valid: boolean;
  message: string;
  labels?: string[];
}

export async function validateTokenClassifierCSV(file: File): Promise<ValidationResult> {
  const accessToken = getAccessToken();
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await axios.post<APIResponse>(
      `${thirdaiPlatformBaseUrl}/api/train/validate-token-classifier-csv`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return {
      valid: true,
      message: response.data.message,
      labels: response.data.data?.labels,
    };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.data) {
      // Type assertion to ensure TypeScript knows the shape of error.response.data
      const errorData = error.response.data as APIResponse;
      return {
        valid: false,
        message: errorData.message || 'Failed to validate CSV file',
      };
    }
    return {
      valid: false,
      message: 'Failed to validate CSV file',
    };
  }
}

interface TrainTokenClassifierParams {
  modelName: string;
  file: File;
  testSplit?: number;
}

export function trainTokenClassifierFromCSV({
  modelName,
  file,
  testSplit = 0.1,
}: TrainTokenClassifierParams): Promise<any> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('test_split', testSplit.toString());

  return new Promise((resolve, reject) => {
    axios
      .post(
        `${thirdaiPlatformBaseUrl}/api/train/train-token-classifier?model_name=${modelName}`,
        formData
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (axios.isAxiosError(err)) {
          const axiosError = err as AxiosError;
          if (axiosError.response && axiosError.response.data) {
            reject(
              new Error(
                (axiosError.response.data as any).detail ||
                  'Failed to train token classification model'
              )
            );
          } else {
            reject(new Error('Failed to train token classification model'));
          }
        } else {
          reject(new Error('Failed to train token classification model'));
        }
      });
  });
}

// types.ts
export interface MetricValues {
  precision: number;
  recall: number;
  fmeasure: number;
}

export interface LabelMetrics {
  [labelName: string]: MetricValues;
}

export interface TrainingExample {
  source: string;
  target: string;
  predictions: string;
  index: number;
}

export interface LabelExamples {
  [labelName: string]: TrainingExample[];
}

export interface ExampleCategories {
  true_positives: LabelExamples;
  false_positives: LabelExamples;
  false_negatives: LabelExamples;
}

export interface TrainReportData {
  before_train_metrics: LabelMetrics;
  after_train_metrics: LabelMetrics;
  after_train_examples: ExampleCategories;
}

export interface TrainReportResponse {
  status: string;
  message: string;
  data: TrainReportData;
}

// api.ts
export function getTrainReport(modelIdentifier: string): Promise<TrainReportResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(
        `${thirdaiPlatformBaseUrl}/api/train/train-report?model_identifier=${encodeURIComponent(modelIdentifier)}`
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export interface EnterpriseSearchOptions {
  retrieval_id: string;
  guardrail_id?: string;
  nlp_classifier_id?: string;
  llm_provider?: string;
  default_mode?: string;
}

interface CreateWorkflowParams {
  workflow_name: string;
  options: EnterpriseSearchOptions;
}

export function create_enterprise_search_workflow({
  workflow_name,
  options,
}: CreateWorkflowParams): Promise<any> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  // Prepare URLSearchParams to pass workflow_name as a query parameter
  const params = new URLSearchParams({
    workflow_name,
  });

  return new Promise((resolve, reject) => {
    axios
      .post(
        `${thirdaiPlatformBaseUrl}/api/workflow/enterprise-search?${params.toString()}`,
        options // Pass the options object as the request body
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        if (err.response && err.response.data) {
          reject(new Error(err.response.data.message || 'Failed to create workflow'));
        } else {
          reject(new Error('Failed to create workflow'));
        }
      });
  });
}

interface KnowledgeExtractionQuestion {
  question: string;
  keywords?: string[];
}

interface KnowledgeExtractionParams {
  model_name: string;
  questions: KnowledgeExtractionQuestion[];
  llm_provider: string;
  advanced_indexing?: boolean;
  rerank?: boolean;
  generate_answers?: boolean;
}

export function create_knowledge_extraction(params: KnowledgeExtractionParams): Promise<any> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/workflow/knowledge-extraction`, params)
      .then((res) => resolve(res.data))
      .catch((err) => {
        reject(
          new Error(err.response?.data?.detail || 'Failed to create knowledge extraction model')
        );
      });
  });
}

export interface Attributes {
  llm_provider?: string;
  default_mode?: string;
  retrieval_id?: string;
  guardrail_id?: string;
  nlp_classifier_id?: string;
}

interface Dependency {
  model_id: string;
  model_name: string;
  type: string;
  sub_type: string;
  username: string;
}

export interface Workflow {
  model_id: string;
  model_name: string;
  type: string;
  sub_type: string;
  train_status: string;
  deploy_status: string;
  publish_date: string;
  username: string;
  user_email: string;
  attributes: Attributes;
  dependencies: Dependency[];
  size: string;
  size_in_memory: string;
}

export function fetchWorkflows(): Promise<Workflow[]> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .get(`${thirdaiPlatformBaseUrl}/api/model/list`)
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

function createModelIdentifier(username: string, model_name: string): string {
  return `${username}/${model_name}`;
}

interface StartWorkflowResponse {
  status_code: number;
  message: string;
  data: {
    models: { id: string; name: string }[];
  };
}

export function start_workflow(
  username: string,
  model_name: string,
  autoscalingEnabled: boolean
): Promise<StartWorkflowResponse> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({
    model_identifier: createModelIdentifier(username, model_name),
    autoscaling_enabled: autoscalingEnabled.toString(), // Convert boolean to string for URL param
  });

  return new Promise((resolve, reject) => {
    axios
      .post<StartWorkflowResponse>(`${thirdaiPlatformBaseUrl}/api/deploy/run?${params.toString()}`)
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

export function stop_workflow(username: string, model_name: string): Promise<StopWorkflowResponse> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/deploy/stop`, null, {
        params: { model_identifier: createModelIdentifier(username, model_name) },
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

export async function delete_workflow(
  username: string,
  model_name: string
): Promise<DeleteWorkflowResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({
    model_identifier: createModelIdentifier(username, model_name),
  });

  return new Promise((resolve, reject) => {
    axios
      .post<DeleteWorkflowResponse>(
        `${thirdaiPlatformBaseUrl}/api/model/delete?${params.toString()}`
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        console.error('Error deleting workflow:', err);
        alert('Error deleting workflow:' + err);
        reject(new Error('Failed to delete workflow'));
      });
  });
}

interface WorkflowDetailsResponse {
  status_code: number;
  message: string;
  data: Workflow;
}

export async function getWorkflowDetails(workflow_id: string): Promise<WorkflowDetailsResponse> {
  const accessToken = getAccessToken();
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ model_id: workflow_id });

  return new Promise((resolve, reject) => {
    axios
      .get<WorkflowDetailsResponse>(
        `${thirdaiPlatformBaseUrl}/api/model/details?${params.toString()}`
      )
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        console.error('Error fetching model details:', err);
        alert('Error fetching model details:' + err);
        reject(new Error('Failed to fetch model details'));
      });
  });
}

export function userEmailLogin(
  email: string,
  password: string,
  setAccessToken: (token: string) => void
): Promise<any> {
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
          localStorage.setItem('username', username);
        }

        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export function userEmailLoginWithAccessToken(
  accessToken: string,
  setAccessToken: (token: string) => void
): Promise<any> {
  console.debug('userEmailLogin called with accessToken:', accessToken);

  return new Promise((resolve, reject) => {
    console.debug('Sending request to /api/user/email-login-with-keycloak with payload:', {
      access_token: accessToken,
    });

    axios
      .post(`${thirdaiPlatformBaseUrl}/api/user/email-login-with-keycloak`, {
        access_token: accessToken,
      })
      .then((res) => {
        console.debug('Response from email-login-with-keycloak:', res);

        const accessToken = res.data.data.access_token;
        const username = res.data.data.user.username;

        if (accessToken) {
          console.debug('Access token received from backend:', accessToken);
          // Store accessToken into local storage, replacing any existing one.
          localStorage.setItem('accessToken', accessToken);
          setAccessToken(accessToken);
        } else {
          console.warn('No access token returned from backend response.');
        }

        if (username) {
          console.debug('Username received from backend:', username);
          localStorage.setItem('username', username);
        } else {
          console.warn('No username found in backend response.');
        }

        resolve(res.data);
      })
      .catch((err) => {
        if (axios.isAxiosError(err)) {
          console.error('Axios error during login:', {
            message: err.message,
            status: err.response?.status,
            data: err.response?.data,
            headers: err.response?.headers,
          });
          console.error('Validation details from backend:', err.response?.data?.detail);
        } else {
          console.error('Unexpected error during login:', err);
        }

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

interface TokenClassificationExample {
  name: string;
  example: string;
  description: string;
}

function tokenClassifierDatagenForm(modelGoal: string, categories: Category[]) {
  const tags = categories.map((category) => ({
    name: category.name,
    examples: category.examples.map((ex) => ex.text),
    description: category.description,
  }));
  return {
    sub_type: 'token',
    task_prompt: modelGoal,
    tags: tags,
  };
}

interface TrainTokenClassifierResponse {
  status_code: number;
  message: string;
  data: {
    model_id: string;
    user_id: string;
  };
}

type Example = {
  text: string;
};

type Category = {
  name: string;
  examples: Example[];
  description: string;
};

export function trainTokenClassifier(
  modelName: string,
  modelGoal: string,
  categories: Category[]
): Promise<TrainTokenClassifierResponse> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken();

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const formData = new FormData();
  formData.append(
    'datagen_options',
    JSON.stringify({
      task_prompt: modelGoal,
      datagen_options: tokenClassifierDatagenForm(modelGoal, categories),
    })
  );

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/train/nlp-datagen?model_name=${modelName}`, formData)
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

interface SentenceClassificationExample {
  name: string;
  example: string;
  description: string;
}

function sentenceClassifierDatagenForm(examples: SentenceClassificationExample[]) {
  const labels = examples.map((example) => ({
    name: example.name,
    examples: [example.example],
    description: example.description,
  }));

  const numSentences = 10_000;
  return {
    sub_type: 'text',
    samples_per_label: Math.max(Math.ceil(numSentences / labels.length), 50),
    target_labels: labels,
  };
}

interface TrainSentenceClassifierResponse {
  status_code: number;
  message: string;
  data: {
    model_id: string;
    user_id: string;
  };
}

export function trainSentenceClassifier(
  modelName: string,
  modelGoal: string,
  examples: SentenceClassificationExample[]
): Promise<TrainSentenceClassifierResponse> {
  // Retrieve the access token from local storage
  const accessToken = getAccessToken();

  // Set the default authorization header for axios
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const formData = new FormData();
  formData.append(
    'datagen_options',
    JSON.stringify({
      task_prompt: modelGoal,
      datagen_options: sentenceClassifierDatagenForm(examples),
    })
  );

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/train/nlp-datagen?model_name=${modelName}`, formData)
      .then((res) => {
        console.log(res);
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

interface UseLabelsOptions {
  deploymentUrl: string;
  maxRecentLabels?: number;
}

interface UseLabelsResult {
  allLabels: Set<string>;
  recentLabels: string[];
  error: Error | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

export function useLabels({
  deploymentUrl,
  maxRecentLabels = 5,
}: UseLabelsOptions): UseLabelsResult {
  const [allLabels, setAllLabels] = useState<Set<string>>(new Set());
  const [recentLabels, setRecentLabels] = useState<string[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const accessToken = getAccessToken();
      axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

      const response = await axios.get<{ data: string[] }>(`${deploymentUrl}/get_labels`);
      const labels = response.data.data;

      setAllLabels((prevLabels) => {
        const newLabels = new Set(prevLabels);
        labels.forEach((label: string) => {
          if (!prevLabels.has(label)) {
            newLabels.add(label);
            setRecentLabels((prev) => [label, ...prev].slice(0, maxRecentLabels));
          }
        });
        return newLabels;
      });

      setError(null);
    } catch (err) {
      console.error('Error fetching labels:', err);
      setError(err instanceof Error ? err : new Error('An unknown error occurred'));
    } finally {
      setIsLoading(false);
    }
  }, [deploymentUrl, maxRecentLabels]);

  return { allLabels, recentLabels, error, isLoading, refresh };
}

interface Sample {
  tokens: string[];
  tags: string[];
}

interface UseRecentSamplesOptions {
  deploymentUrl: string;
  maxRecentSamples?: number;
}

interface UseRecentSamplesResult {
  recentSamples: Sample[];
  error: Error | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

export function useRecentSamples({
  deploymentUrl,
  maxRecentSamples = 5,
}: UseRecentSamplesOptions): UseRecentSamplesResult {
  const [recentSamples, setRecentSamples] = useState<Sample[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const accessToken = getAccessToken();
      axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

      const response = await axios.get<{ data: Sample[] }>(`${deploymentUrl}/get_recent_samples`);
      setRecentSamples(response.data.data.slice(0, maxRecentSamples));
      setError(null);
    } catch (err) {
      console.error('Error fetching recent samples:', err);
      setError(err instanceof Error ? err : new Error('An unknown error occurred'));
    } finally {
      setIsLoading(false);
    }
  }, [deploymentUrl, maxRecentSamples]);

  return { recentSamples, error, isLoading, refresh };
}

export interface TokenClassificationResult {
  query_text: string;
  tokens: string[];
  predicted_tags: string[][];
}
export interface PredictionResponse {
  prediction_results: TokenClassificationResult;
  time_taken: number;
}

export interface InsertSamplePayload {
  tokens: string[];
  tags: string[];
}

export function useTokenClassificationEndpoints() {
  const accessToken = useAccessToken();
  const params = useParams();
  // console.log(params);
  const workflowId = params.deploymentId as string;
  const [workflowName, setWorkflowName] = useState<string>('');
  const [deploymentUrl, setDeploymentUrl] = useState<string | undefined>();

  // console.log('PARAMS', params);

  useEffect(() => {
    const init = async () => {
      const accessToken = getAccessToken();
      axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

      const params = new URLSearchParams({ model_id: workflowId });

      axios
        .get<WorkflowDetailsResponse>(
          `${thirdaiPlatformBaseUrl}/api/model/details?${params.toString()}`
        )
        .then((res) => {
          setWorkflowName(res.data.data.model_name);
          if (res.data.data.model_id) {
            setDeploymentUrl(`${deploymentBaseUrl}/${res.data.data.model_id}`);
          }
        })
        .catch((err) => {
          console.error('Error fetching workflow details:', err);
          alert('Error fetching workflow details:' + err);
        });
    };
    init();
  }, []);

  const predict = async (query: string): Promise<PredictionResponse> => {
    // Set the default authorization header for axios
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    try {
      const response = await axios.post(`${deploymentUrl}/predict`, {
        text: query,
        top_k: 1,
      });
      return response.data.data;
    } catch (error) {
      console.error('Error predicting tokens:', error);
      alert('Error predicting tokens:' + error);
      throw new Error('Failed to predict tokens');
    }
  };

  const formatTime = (timeSeconds: number) => {
    const timeMinutes = Math.floor(timeSeconds / 60);
    const timeHours = Math.floor(timeMinutes / 60);
    const timeDays = Math.floor(timeHours / 24);
    return `${timeDays} days ${timeHours % 24} hours ${timeMinutes % 60} minutes ${timeSeconds % 60} seconds`;
  };

  const formatAmount = (amount: number) => {
    if (amount < 1000) {
      return amount.toString();
    }
    let suffix = '';
    if (amount >= 1000000000) {
      amount /= 1000000000;
      suffix = ' B';
    } else if (amount >= 1000000) {
      amount /= 1000000;
      suffix = ' M';
    } else {
      amount /= 1000;
      suffix = ' K';
    }
    let amountstr = amount.toString();
    if (amountstr.includes('.')) {
      const [wholes, decimals] = amountstr.split('.');
      const decimalsLength = 3 - Math.min(3, wholes.length);
      amountstr = decimalsLength ? wholes + '.' + decimals.substring(0, decimalsLength) : wholes;
    }
    return amountstr + suffix;
  };

  const getStats =
    deploymentUrl &&
    (async (): Promise<DeploymentStats> => {
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
            ],
          },
          throughput: {
            header: [
              'Time Period',
              'Tokens Identified',
              'Queries Ingested',
              'Queries Ingested Size',
            ],
            rows: [
              [
                'Past hour',
                formatAmount(response.data.data.past_hour.tokens_identified),
                formatAmount(response.data.data.past_hour.queries_ingested),
                formatAmount(response.data.data.past_hour.queries_ingested_bytes) + 'B',
              ],
              [
                'Total',
                formatAmount(response.data.data.total.tokens_identified),
                formatAmount(response.data.data.total.queries_ingested),
                formatAmount(response.data.data.total.queries_ingested_bytes) + 'B',
              ],
            ],
          },
        };
      } catch (error) {
        console.error('Error fetching stats:', error);
        alert('Error fetching stats:' + error);
        throw new Error('Error fetching stats.');
      }
    });

  const insertSample = async (sample: InsertSamplePayload): Promise<void> => {
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    try {
      await axios.post(`${deploymentUrl}/insert_sample`, sample);
    } catch (error) {
      console.error('Error inserting sample:', error);
      alert('Error inserting sample:' + error);
      throw new Error('Failed to insert sample');
    }
  };

  const addLabel = async (labels: {
    tags: { name: string; description: string }[];
  }): Promise<void> => {
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    try {
      await axios.post(`${deploymentUrl}/add_labels`, labels);
    } catch (error) {
      console.error('Error adding label:', error);
      alert('Error adding label:' + error);
      throw new Error('Failed to add label');
    }
  };

  const getLabels = async (): Promise<string[]> => {
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    try {
      const response = await axios.get(`${deploymentUrl}/get_labels`);
      return response.data.data;
    } catch (error) {
      console.error('Error fetching labels:', error);
      alert('Error fetching labels:' + error);
      throw new Error('Failed to fetch labels');
    }
  };

  const getTextFromFile = async (file: File): Promise<string[]> => {
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${deploymentUrl}/get-text`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data.data;
    } catch (error) {
      console.error('Error parsing file:', error);
      alert('Error parsing file:' + error);
      throw new Error('Failed to parse file');
    }
  };

  return {
    workflowName,
    predict,
    insertSample,
    addLabel,
    getLabels,
    getTextFromFile,
    getStats,
  };
}

interface TextClassificationResult {
  query_text: string;
  predicted_classes: [string, number][];
}

interface PredictionResult {
  status: string;
  message: string;
  data: {
    prediction_results: {
      query_text: string;
      predicted_classes: [string, number][];
    };
    time_taken: number;
  };
}

export function useTextClassificationEndpoints() {
  const accessToken = useAccessToken();
  const params = useParams();
  const workflowId = params.deploymentId as string;
  const [workflowName, setWorkflowName] = useState<string>('');
  const [deploymentUrl, setDeploymentUrl] = useState<string | undefined>();

  console.log('PARAMS', params);

  useEffect(() => {
    const init = async () => {
      const accessToken = getAccessToken();
      axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

      const params = new URLSearchParams({ model_id: workflowId });

      axios
        .get<WorkflowDetailsResponse>(
          `${thirdaiPlatformBaseUrl}/api/model/details?${params.toString()}`
        )
        .then((res) => {
          setWorkflowName(res.data.data.model_name);
          setDeploymentUrl(`${deploymentBaseUrl}/${res.data.data.model_id}`);
        })
        .catch((err) => {
          console.error('Error fetching workflow details:', err);
          alert('Error fetching workflow details:' + err);
        });
    };
    init();
  }, []);

  const predict = async (query: string): Promise<PredictionResult> => {
    // Set the default authorization header for axios
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

    try {
      const response = await axios.post<PredictionResult>(`${deploymentUrl}/predict`, {
        text: query,
        top_k: 5,
      });

      // Return the full response data structure
      return response.data;
    } catch (error) {
      console.error('Error predicting tokens:', error);
      alert('Error predicting tokens:' + error);
      throw new Error('Failed to predict tokens');
    }
  };

  const getTextFromFile = async (file: File): Promise<string[]> => {
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${deploymentUrl}/get-text`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data.data;
    } catch (error) {
      console.error('Error parsing file:', error);
      alert('Error parsing file:' + error);
      throw new Error('Failed to parse file');
    }
  };

  return {
    workflowName,
    getTextFromFile,
    predict,
  };
}

export function useSentimentClassification(workflowId: string | null) {
  const accessToken = useAccessToken(); // Assuming this function exists
  const [deploymentUrl, setDeploymentUrl] = useState<string | undefined>();

  useEffect(() => {
    if (!workflowId) return;

    const init = async () => {
      try {
        setDeploymentUrl(`${deploymentBaseUrl}/${workflowId}`);
      } catch (error) {
        console.error('Error fetching sentiment model details:', error);
        alert('Error fetching sentiment model details: ' + error);
      }
    };

    init();
  }, [workflowId, accessToken]);

  // Function to predict sentiment based on the input query
  const predictSentiment = async (query: string): Promise<TextClassificationResult> => {
    if (!deploymentUrl) {
      throw new Error('Sentiment classifier deployment URL not set');
    }

    try {
      // Corrected the key from 'query' to 'text'
      const response = await axios.post(`${deploymentUrl}/predict`, { text: query, top_k: 5 });
      return response.data.data;
    } catch (error) {
      console.error('Error predicting sentiment:', error);
      alert('Error predicting sentiment: ' + error);
      throw new Error('Failed to predict sentiment');
    }
  };

  // Return the predict function
  return {
    predictSentiment,
  };
}

export interface Question {
  question_id: string;
  question_text: string;
  keywords: string[];
}

export interface Report {
  id: string;
  name: string;
  content: string;
}

export interface WorkFlowDetails {
  model_name: string;
  model_id: string;
}

export function useKnowledgeExtractionEndpoints(workflowId: string | null) {
  const accessToken = useAccessToken();
  const deploymentUrl = workflowId ? `${deploymentBaseUrl}/${workflowId}` : undefined;

  const createReport = async (files: File[]): Promise<string> => {
    if (!deploymentUrl) throw new Error('Knowledge extraction deployment URL not set');

    const formData = new FormData();
    const documents = files.map(file => ({
      name: file.name,
      path: file.name,
      location: 'local'
    }));
    formData.append('documents', JSON.stringify({ documents }));
    files.forEach((file) => formData.append('files', file));

    try {
      const accessToken = getAccessToken();
      const response = await axios.post(`${deploymentUrl}/report/create`, formData, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data.data.report_id;
    } catch (error) {
      console.error('Error creating report:', error);
      throw new Error('Failed to create report');
    }
  };

  const getReport = async (reportId: string): Promise<Report> => {
    if (!deploymentUrl) throw new Error('Knowledge extraction deployment URL not set');
    try {
      const accessToken = getAccessToken();
      const response = await axios.get<{ data: Report }>(`${deploymentUrl}/report/${reportId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      return response.data.data;
    } catch (error) {
      console.error('Error getting report:', error);
      throw new Error('Failed to get report');
    }
  };

  const deleteReport = async (reportId: string): Promise<void> => {
    if (!deploymentUrl) throw new Error('Knowledge extraction deployment URL not set');
    try {
      const accessToken = getAccessToken();
      await axios.delete(`${deploymentUrl}/report/${reportId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
    } catch (error) {
      console.error('Error deleting report:', error);
      throw new Error('Failed to delete report');
    }
  };

  const addQuestion = async (question: string, keywords?: string[]): Promise<string> => {
    if (!deploymentUrl) throw new Error('Knowledge extraction deployment URL not set');
    try {
      const accessToken = getAccessToken();
      const response = await axios.post(
        `${deploymentUrl}/questions`,
        { question, keywords },
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      );
      return response.data.data.question_id;
    } catch (error) {
      console.error('Error adding question:', error);
      throw new Error('Failed to add question');
    }
  };

  const getQuestions = async (): Promise<Question[]> => {
    if (!deploymentUrl) throw new Error('Knowledge extraction deployment URL not set');
    try {
      const accessToken = getAccessToken();
      const response = await axios.get<{
        status: string;
        message: string;
        data: Question[];
      }>(`${deploymentUrl}/questions`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      return response.data.data;
    } catch (error) {
      console.error('Error getting questions:', error);
      throw new Error('Failed to get questions');
    }
  };

  const deleteQuestion = async (questionId: string): Promise<void> => {
    if (!deploymentUrl) throw new Error('Knowledge extraction deployment URL not set');
    try {
      const accessToken = getAccessToken();
      await axios.delete(`${deploymentUrl}/questions/${questionId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
    } catch (error) {
      console.error('Error deleting question:', error);
      throw new Error('Failed to delete question');
    }
  };

  const editQuestion = async (
    questionId: string,
    newQuestion: string,
    keywords?: string[]
  ): Promise<string> => {
    await deleteQuestion(questionId);
    return addQuestion(newQuestion, keywords);
  };

  return {
    createReport,
    getReport,
    deleteReport,
    addQuestion,
    getQuestions,
    deleteQuestion,
    editQuestion,
  };
}

export async function piiDetect(
  query: string,
  workflowId: string
): Promise<TokenClassificationResult> {
  try {
    // Corrected the key from 'query' to 'text'
    const response = await axios.post(`${deploymentBaseUrl}/${workflowId}/predict`, {
      text: query,
      top_k: 1,
    });
    return response.data.data;
  } catch (error) {
    console.error('Error performing pii detection:', error);
    alert('Error performing pii detection: ' + error);
    throw new Error('Failed to perform pii detection');
  }
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
  verified: boolean;
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
      .get(`${thirdaiPlatformBaseUrl}/api/model/list`)
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
      .get(`${thirdaiPlatformBaseUrl}/api/user/list`)
      .then((res) => {
        resolve(res.data);
      })
      .catch((err) => {
        reject(err);
      });
  });
}

export async function verifyUser(email: string): Promise<void> {
  const accessToken = getAccessToken();

  return axios.post(
    `${thirdaiPlatformBaseUrl}/api/user/verify-user`,
    { email },
    { headers: { Authorization: `Bearer ${accessToken}` } }
  );
}

// MODEL //

export async function updateModelAccessLevel(
  model_identifier: string,
  access_level: 'private' | 'protected' | 'public',
  team_id?: string
): Promise<void> {
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
        alert('Error updating model access level:' + err);
        reject(err);
      });
  });
}

export async function deleteModel(model_identifier: string): Promise<void> {
  const accessToken = getAccessToken(); // Ensure this function is implemented elsewhere in your codebase

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

  const params = new URLSearchParams({ model_identifier });

  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/model/delete?${params.toString()}`)
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error deleting model:', err);
        alert('Error deleting model:' + err);
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
        alert('Error removing user from team:' + err);
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
        alert('Error deleting team:' + err);
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
        alert('Error deleting user:' + err);
        reject(err);
      });
  });
}

export interface AddUserPayload {
  username: string;
  email: string;
  password: string;
}

export interface AddUserResponse {
  message: string;
  data?: {
    user_id: string;
    email: string;
  };
}

export async function addUser(userData: AddUserPayload): Promise<AddUserResponse> {
  const accessToken = getAccessToken();

  return new Promise((resolve, reject) => {
    axios
      .post<AddUserResponse>(`${thirdaiPlatformBaseUrl}/api/user/add-user`, userData, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      .then((response) => {
        resolve(response.data);
      })
      .catch((err) => {
        console.error('Error adding user:', err);
        reject(err);
      });
  });
}

export async function promoteUserToGlobalAdmin(email: string): Promise<void> {
  const accessToken = getAccessToken();

  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
  return new Promise((resolve, reject) => {
    axios
      .post(`${thirdaiPlatformBaseUrl}/api/user/add-global-admin`, { email: email })
      .then(() => {
        resolve();
      })
      .catch((err) => {
        console.error('Error promoting user:', err);
        alert('Error promoting user:' + err);
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
        alert('Error updating model:' + err);
        reject(err);
      });
  });
}

export interface Team {
  team_id: string;
  team_name: string;
  role: 'user' | 'team_admin' | 'global_admin';
}

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

  const params = new URLSearchParams({ model_id: modelId });

  try {
    const response = await axios.get(`${deploymentBaseUrl}/cache/token?${params.toString()}`);
    return response.data.access_token; // Assuming the backend returns the data directly
  } catch (err) {
    console.error('Error getting temporary cache access token:', err);
    throw err; // Re-throwing the error to handle it in the component
  }
}

export async function fetchFeedback(username: string, modelName: string) {
  const modelIdentifier = `${username}/${modelName}`;
  const accessToken = getAccessToken();

  try {
    const response = await axios({
      method: 'get',
      url: `${deploymentBaseUrl}/api/deploy/feedbacks`,
      params: {
        model_identifier: modelIdentifier,
      },
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    return response?.data?.data;
  } catch (error) {
    console.error('Error getting Feedback Response:', error);
    throw error;
  }
}
