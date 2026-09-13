/**
 * Zustand store — replaces Streamlit's st.session_state.
 * Single source of truth for the entire app.
 */
import { create } from 'zustand';
import type { AttritionStep, CodeEntry, CodingSystem } from '../types';

let _idCounter = 0;
export const uid = () => `id_${++_idCounter}_${Math.random().toString(36).slice(2, 7)}`;

// ─── State shape ─────────────────────────────────────────────────────────────
interface AppState {
  // Protocol metadata
  title: string;
  dataSources: string[];
  studyWindow: string;
  inputMode: null | 'upload' | 'manual' | 'text';
  parseMethod: string;
  parsedSummary: string;
  parseWarnings: string[];

  // Attrition steps (editable)
  steps: AttritionStep[];

  // Code lists
  codeLists: CodeEntry[];
  selectedConditions: string[] | null; // null = all selected

  // Notebook output
  notebookPath: string;          // editable workspace path
  notebookSql: string;
  notebookUrl: string;
  notebookWarnings: string[];

  // Databricks connection
  dbxConnected: boolean;
  dbxUser: string;
  dbxIsDatabricksApp: boolean;
  dbxNotebookRoot: string;   // /Shared/ads_automation — team-wide notebook folder

  // UI loading flags
  isParsing: boolean;
  isGenerating: boolean;

  // ── Actions ──
  setTitle: (t: string) => void;
  setDataSources: (s: string[]) => void;
  setStudyWindow: (w: string) => void;
  setInputMode: (m: AppState['inputMode']) => void;
  setParseResult: (p: {
    title: string;
    dataSources: string[];
    studyWindow: string;
    steps: AttritionStep[];
    parseMethod: string;
    parsedSummary: string;
    warnings: string[];
    inputMode: AppState['inputMode'];
  }) => void;

  // Steps
  setSteps: (steps: AttritionStep[]) => void;
  addStep: () => void;
  updateStep: (id: string, field: 'step_type' | 'description', value: string) => void;
  removeStep: (id: string) => void;
  moveStep: (id: string, dir: 'up' | 'down') => void;

  // Code lists
  addCodeEntries: (entries: Omit<CodeEntry, 'id'>[]) => void;
  removeCodeGroup: (condition: string, system: CodingSystem) => void;
  clearCodeLists: () => void;
  setSelectedConditions: (c: string[] | null) => void;

  // Notebook
  setNotebookPath: (p: string) => void;
  setNotebookResult: (sql: string, url: string, warnings: string[]) => void;

  // Databricks
  setDbxStatus: (connected: boolean, user: string, isApp: boolean, notebookRoot?: string) => void;

  // Loading
  setIsParsing: (v: boolean) => void;
  setIsGenerating: (v: boolean) => void;

  // Reset
  resetProtocol: () => void;
}

// ─── Store ───────────────────────────────────────────────────────────────────
export const useStore = create<AppState>((set) => ({
  // Initial state
  title: '',
  dataSources: [],
  studyWindow: '',
  inputMode: null,
  parseMethod: '',
  parsedSummary: '',
  parseWarnings: [],

  steps: [],
  codeLists: [],
  selectedConditions: null,

  notebookPath: '',
  notebookSql: '',
  notebookUrl: '',
  notebookWarnings: [],

  dbxConnected: false,
  dbxUser: '',
  dbxIsDatabricksApp: false,
  dbxNotebookRoot: '/Shared/ads_automation',

  isParsing: false,
  isGenerating: false,

  // ── Actions ──
  setTitle: (t) => set({ title: t }),
  setDataSources: (s) => set({ dataSources: s }),
  setStudyWindow: (w) => set({ studyWindow: w }),
  setInputMode: (m) => set({ inputMode: m }),

  setParseResult: ({ title, dataSources, studyWindow, steps, parseMethod, parsedSummary, warnings, inputMode }) =>
    set({
      title,
      dataSources,
      studyWindow,
      steps,
      parseMethod,
      parsedSummary,
      parseWarnings: warnings,
      inputMode,
    }),

  // Steps
  setSteps: (steps) => set({ steps }),

  addStep: () =>
    set((s) => ({
      steps: [
        ...s.steps,
        { id: uid(), step_type: 'inclusion', description: '' },
      ],
    })),

  updateStep: (id, field, value) =>
    set((s) => ({
      steps: s.steps.map((step) =>
        step.id === id ? { ...step, [field]: value } : step,
      ),
    })),

  removeStep: (id) =>
    set((s) => ({ steps: s.steps.filter((step) => step.id !== id) })),

  moveStep: (id, dir) =>
    set((s) => {
      const idx = s.steps.findIndex((st) => st.id === id);
      if (idx < 0) return s;
      const next = [...s.steps];
      const swap = dir === 'up' ? idx - 1 : idx + 1;
      if (swap < 0 || swap >= next.length) return s;
      [next[idx], next[swap]] = [next[swap], next[idx]];
      return { steps: next };
    }),

  // Code lists
  addCodeEntries: (entries) =>
    set((s) => {
      const newEntries = entries.map((e) => ({ ...e, id: uid() }));
      const updated = [...s.codeLists, ...newEntries];
      // Auto-select any new conditions
      const allConds = [...new Set(updated.map((e) => e.condition))];
      const prevSel = new Set(s.selectedConditions ?? allConds);
      const newConds = allConds.filter((c) => !prevSel.has(c));
      const selected = [...(s.selectedConditions ?? []), ...newConds];
      return {
        codeLists: updated,
        selectedConditions: selected.length ? selected : null,
      };
    }),

  removeCodeGroup: (condition, system) =>
    set((s) => ({
      codeLists: s.codeLists.filter(
        (e) => !(e.condition === condition && e.coding_system === system),
      ),
    })),

  clearCodeLists: () => set({ codeLists: [], selectedConditions: null }),

  setSelectedConditions: (c) => set({ selectedConditions: c }),

  // Notebook
  setNotebookPath: (p) => set({ notebookPath: p }),
  setNotebookResult: (sql, url, warnings) =>
    set({ notebookSql: sql, notebookUrl: url, notebookWarnings: warnings }),

  // Databricks
  setDbxStatus: (connected, user, isApp, notebookRoot) =>
    set({
      dbxConnected: connected,
      dbxUser: user,
      dbxIsDatabricksApp: isApp,
      ...(notebookRoot ? { dbxNotebookRoot: notebookRoot } : {}),
    }),

  // Loading
  setIsParsing: (v) => set({ isParsing: v }),
  setIsGenerating: (v) => set({ isGenerating: v }),

  // Reset
  resetProtocol: () =>
    set({
      title: '',
      dataSources: [],
      studyWindow: '',
      inputMode: null,
      parseMethod: '',
      parsedSummary: '',
      parseWarnings: [],
      steps: [],
      codeLists: [],
      selectedConditions: null,
      notebookPath: '',
      notebookSql: '',
      notebookUrl: '',
      notebookWarnings: [],
    }),
}));

// ─── Derived selectors ───────────────────────────────────────────────────────
export const selInclusionCount = (s: AppState) =>
  s.steps.filter((st) => st.step_type === 'inclusion').length;

export const selExclusionCount = (s: AppState) =>
  s.steps.filter((st) => st.step_type === 'exclusion').length;

export const selTotalCount = (s: AppState) =>
  s.steps.filter((st) => st.description.trim()).length;

export const selAllConditions = (s: AppState) =>
  [...new Set(s.codeLists.map((e) => e.condition))].sort();
