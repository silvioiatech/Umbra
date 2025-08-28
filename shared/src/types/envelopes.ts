// Core envelope types from UMBRA_FINAL_V2.md specification
export interface Envelope<TPayload> {
  reqId: string;            // uuid
  userId: string;           // telegram id
  lang: 'EN' | 'FR' | 'PT';
  timestamp: string;        // ISO
  payload: TPayload;
  meta?: {
    costCapUsd?: number;
    priority?: 'normal' | 'urgent';
    retryCount?: number;
  };
}

export interface ModuleResult<T> {
  reqId: string;
  status: 'success' | 'error' | 'needs_validation' | 'processing';
  data?: T;
  error?: {
    type: 'functional' | 'technical' | 'conflict' | 'auth';
    code: string;
    message: string;
    retryable: boolean;
  };
  audit?: {
    module: string;
    durationMs: number;
    provider?: string;
    tokenUsage?: number;
    costUsd?: number;
  };
}

// Language support types
export type SupportedLanguage = 'EN' | 'FR' | 'PT';

// Priority levels
export type Priority = 'normal' | 'urgent';

// Error types
export type ErrorType = 'functional' | 'technical' | 'conflict' | 'auth';

// Module status types
export type ModuleStatus = 'success' | 'error' | 'needs_validation' | 'processing';

// Base envelope payload interface
export interface BasePayload {
  action: string;
  [key: string]: any;
}

// Validation token interface for critical operations
export interface ValidationToken {
  token: string;
  userId: string;
  action: string;
  expiresAt: string;
  validated: boolean;
}