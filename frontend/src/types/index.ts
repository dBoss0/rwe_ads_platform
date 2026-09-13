// ─── Coding Systems ──────────────────────────────────────────────────────────
export const CODING_SYSTEMS = [
  'ICD-9 CM', 'ICD-9 PCS',
  'ICD-10 CM', 'ICD-10 PCS',
  'CPT-4', 'CPT-5',
  'HCPCS', 'DRG', 'NDC',
] as const;

export type CodingSystem = typeof CODING_SYSTEMS[number];

export const CODING_SYSTEM_STYLE: Record<CodingSystem, { border: string; bg: string }> = {
  'ICD-9 CM':   { border: '#7c3aed', bg: 'rgba(124,58,237,0.07)' },
  'ICD-9 PCS':  { border: '#6d28d9', bg: 'rgba(109,40,217,0.07)' },
  'ICD-10 CM':  { border: '#0f68b2', bg: 'rgba(15,104,178,0.08)' },
  'ICD-10 PCS': { border: '#1d4ed8', bg: 'rgba(29,78,216,0.08)' },
  'CPT-4':      { border: '#328714', bg: 'rgba(50,135,20,0.07)' },
  'CPT-5':      { border: '#15803d', bg: 'rgba(21,128,61,0.07)' },
  'HCPCS':      { border: '#0891b2', bg: 'rgba(8,145,178,0.07)' },
  'DRG':        { border: '#ea580c', bg: 'rgba(234,88,12,0.07)' },
  'NDC':        { border: '#eb1700', bg: 'rgba(235,23,0,0.07)' },
};

// ─── Attrition Steps ─────────────────────────────────────────────────────────
export interface AttritionStep {
  id: string;                                  // React key (UUID)
  step_type: 'inclusion' | 'exclusion';
  description: string;
  criterion_type?: string;
  raw_text?: string;
  step_num?: number;
}

// ─── Code Lists ──────────────────────────────────────────────────────────────
export interface CodeEntry {
  id: string;              // React key (UUID)
  condition: string;
  coding_system: CodingSystem;
  code: string;
  description: string;
}

// ─── API: Parse Protocol ─────────────────────────────────────────────────────
export interface APIAttritionStep {
  step_num: number;
  step_type: 'inclusion' | 'exclusion';
  description: string;
  criterion_type: string;
  raw_text: string;
}

export interface ParseResponse {
  title: string;
  data_sources: string[];
  study_window: string;
  all_steps: APIAttritionStep[];
  inclusion_steps: APIAttritionStep[];
  exclusion_steps: APIAttritionStep[];
  parse_method: string;
  warnings: string[];
  summary?: string;
}

// ─── API: Notebook Generation ─────────────────────────────────────────────────
export interface CodeListInput {
  condition: string;
  codes: string[];
  coding_system: CodingSystem;
  code_descriptions?: string[];
}

export interface StepInput {
  step_num: number;
  step_type: 'inclusion' | 'exclusion';
  description: string;
  criterion_type?: string;
  code_list?: CodeListInput;
}

export interface NotebookRequest {
  title: string;
  steps: StepInput[];
  code_lists: CodeListInput[];
  study_window?: string;
  workspace_path?: string;
}

export interface StepSQL {
  step_num: number;
  step_type: string;
  description: string;
  sql: string;
  generated_by: 'llm' | 'fallback';
}

export interface NotebookResponse {
  title: string;
  notebook_sql: string;
  steps: StepSQL[];
  workspace_url?: string;
  warnings: string[];
}

// ─── Health ──────────────────────────────────────────────────────────────────
export interface HealthResponse {
  status: string;
  databricks_connected: boolean;
  is_databricks_app: boolean;
  user?: string;
  version: string;
  notebook_workspace_root?: string;
}
