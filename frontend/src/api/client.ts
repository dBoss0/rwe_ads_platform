/**
 * API client — all calls to FastAPI at /api/*
 * In dev: Vite proxy forwards /api → localhost:8000
 * In production (Databricks App): same origin
 */
import type {
  ParseResponse,
  NotebookRequest,
  NotebookResponse,
  HealthResponse,
} from '../types';

const BASE = '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ─── Health ──────────────────────────────────────────────────────────────────
export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/health`);
  return handleResponse<HealthResponse>(res);
}

// ─── Protocol Parse ──────────────────────────────────────────────────────────
/**
 * Parse protocol from raw pasted text.
 */
export async function parseProtocolText(text: string): Promise<ParseResponse> {
  const res = await fetch(`${BASE}/protocol/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: text }),  // backend field is raw_text
  });
  return handleResponse<ParseResponse>(res);
}

/**
 * Upload a DOCX/PDF file for LLM parsing.
 */
export async function uploadProtocol(file: File): Promise<ParseResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/protocol/upload`, {
    method: 'POST',
    body: form,
  });
  return handleResponse<ParseResponse>(res);
}

// ─── Attrition Notebook ──────────────────────────────────────────────────────
/**
 * Generate (and optionally push) the attrition SQL notebook.
 */
export async function generateNotebook(
  req: NotebookRequest,
): Promise<NotebookResponse> {
  const res = await fetch(`${BASE}/attrition/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return handleResponse<NotebookResponse>(res);
}

/**
 * Download the notebook SQL as a file (returns blob URL).
 */
export async function downloadNotebookSql(
  title: string,
  notebook_sql: string,
): Promise<void> {
  const safe = title.replace(/[^a-z0-9]+/gi, '_').slice(0, 60) || 'attrition';
  const blob = new Blob([notebook_sql], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${safe}_attrition.sql`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Catalog ─────────────────────────────────────────────────────────────────
export async function getCatalogTables(): Promise<{ tables: string[] }> {
  const res = await fetch(`${BASE}/catalog/tables`);
  return handleResponse<{ tables: string[] }>(res);
}
