import { BasePayload } from './envelopes';

// Umbra Main Agent payloads
export interface UmbraPayload extends BasePayload {
  action: 'classify' | 'route' | 'execute' | 'clarify';
  message?: string;
  intent?: string;
  confidence?: number;
  targetModule?: string;
}

// Finance Module payloads
export interface FinancePayload extends BasePayload {
  action: 'ocr' | 'extract' | 'categorize' | 'report' | 'deduplicate';
  documentUrl?: string;
  documentType?: 'invoice' | 'receipt' | 'statement' | 'payroll';
  reportType?: 'budget' | 'vat' | 'tax';
  dateRange?: {
    start: string;
    end: string;
  };
}

// VPS Concierge payloads  
export interface ConciergePayload extends BasePayload {
  action: 'monitor' | 'execute' | 'validate' | 'client_management';
  command?: string;
  script?: string;
  validationToken?: string;
  clientAction?: 'create' | 'delete' | 'list';
  clientName?: string;
  clientPort?: number;
}

// Business Module payloads
export interface BusinessPayload extends BasePayload {
  action: 'manage_client' | 'delegate_workflow' | 'track_inventory';
  clientName?: string;
  clientPort?: number;
  workflowSpec?: any;
  operationType?: 'create' | 'update' | 'delete' | 'list';
}

// Production Module payloads
export interface ProductionPayload extends BasePayload {
  action: 'create_workflow' | 'validate' | 'deploy' | 'rollback';
  workflowName?: string;
  workflowSpec?: any;
  nlDescription?: string;
  environment?: 'staging' | 'production';
  version?: string;
}

// Creator Module payloads
export interface CreatorPayload extends BasePayload {
  action: 'generate_text' | 'generate_image' | 'generate_video' | 'generate_audio' | 'edit_video';
  provider?: 'openrouter' | 'runway' | 'shotstack' | 'elevenlabs';
  prompt?: string;
  mediaType?: 'text' | 'image' | 'video' | 'audio';
  parameters?: {
    duration?: number;
    resolution?: string;
    voice?: string;
    style?: string;
  };
}

// MCP Service payloads
export interface MCPPayload extends BasePayload {
  action: 'validate' | 'dry_run' | 'import' | 'enable' | 'test_run' | 'promote' | 'export' | 'rollback';
  workflowJson?: any;
  workflowId?: string;
  environment?: 'staging' | 'production';
  version?: string;
}

// Union type for all module payloads
export type ModulePayload = 
  | UmbraPayload
  | FinancePayload  
  | ConciergePayload
  | BusinessPayload
  | ProductionPayload
  | CreatorPayload
  | MCPPayload;

// Module response data types
export interface FinanceResult {
  extractedData?: {
    vendor?: string;
    amount?: number;
    date?: string;
    category?: string;
    confidence?: number;
  };
  reportData?: any;
  anomalies?: string[];
}

export interface BusinessResult {
  clientList?: Array<{
    name: string;
    port: number;
    status: string;
    url?: string;
    containerInfo?: any;
  }>;
  workflowStatus?: {
    delegated: boolean;
    targetModule: string;
    taskId?: string;
  };
  inventoryData?: any;
  operationResult?: any;
  timestamp?: string;
}

export interface ConciergeResult {
  systemStatus?: any;
  executionResult?: any;
  containerResult?: any;
  validationResult?: any;
  commandOutput?: string;
  clientList?: Array<{
    name: string;
    port: number;
    status: string;
    url?: string;
  }>;
  timestamp?: string;
}

export interface ProductionResult {
  workflowId?: string;
  status?: 'created' | 'validated' | 'deployed' | 'failed';
  validationErrors?: string[];
  testResults?: any;
}

export interface CreatorResult {
  mediaUrl?: string;
  mediaType?: string;
  metadata?: {
    duration?: number;
    size?: number;
    provider?: string;
  };
}

export interface MCPResult {
  workflowId?: string;
  version?: string;
  status?: 'validated' | 'imported' | 'enabled' | 'promoted';
  errors?: string[];
}