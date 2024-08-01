import 'server-only';

export type SelectModel = {
  id: string;
  model_name: string;
  train_status: string; // Assuming "status" is a custom enum or type, adjust if needed
  type: string;
  sub_type?: string | null; // Optional field, can be null
  downloads: number;
  access_level: string; // Assuming "access" is a custom enum or type, adjust if needed
  domain?: string | null; // Optional field, can be null
  publish_date?: string | null; // Optional field, can be null
  parent_id?: string | null; // Optional field, can be null
  parent_deployment_id?: string | null; // Optional field, can be null
  user_id: string;
};