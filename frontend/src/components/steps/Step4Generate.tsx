/**
 * Step 4 — Generate Notebook.
 *
 * Features:
 *  - Workspace path input (editable, auto-populated from title)
 *  - "Generate & Push to Databricks" button → POST /api/attrition/generate
 *  - "Download SQL" button — saves file locally without Databricks
 *  - Success banner with clickable notebook URL
 *  - Step preview card (numbered rows with INC/EXC badge)
 *  - Per-step LLM vs fallback indicators
 *  - Warning list for fallback steps
 */
import { useState, useEffect } from 'react'
import { useStore, selAllConditions } from '../../store/useStore'
import { generateNotebook, downloadNotebookSql } from '../../api/client'
import type { NotebookRequest, StepInput, CodeListInput } from '../../types'
import { CODING_SYSTEM_STYLE } from '../../types'

export function Step4Generate() {
  const inputMode = useStore((s) => s.inputMode)
  if (!inputMode) return null

  return (
    <section>
      <div className="section-header">
        <div className="step-num">4</div>
        <div>
          <div className="section-title">Generate Notebook</div>
          <span className="section-title-sub">Generates a Databricks SQL attrition notebook and pushes it to your workspace</span>
        </div>
      </div>
      <GenerateBody />
    </section>
  )
}

function GenerateBody() {
  const title          = useStore((s) => s.title)
  const steps          = useStore((s) => s.steps)
  const codeLists      = useStore((s) => s.codeLists)
  const selectedConds  = useStore((s) => s.selectedConditions)
  const allConds       = useStore(selAllConditions)
  const studyWindow    = useStore((s) => s.studyWindow)
  const dbxUser        = useStore((s) => s.dbxUser)
  const dbxConnected   = useStore((s) => s.dbxConnected)
  const isGenerating   = useStore((s) => s.isGenerating)
  const setIsGenerating = useStore((s) => s.setIsGenerating)
  const notebookSql    = useStore((s) => s.notebookSql)
  const notebookUrl    = useStore((s) => s.notebookUrl)
  const notebookWarnings = useStore((s) => s.notebookWarnings)
  const setNotebookResult = useStore((s) => s.setNotebookResult)
  const setNotebookPath   = useStore((s) => s.setNotebookPath)
  const storedPath     = useStore((s) => s.notebookPath)

  const [error, setError] = useState<string | null>(null)
  const [stepSQLs, setStepSQLs] = useState<Array<{ step_num: number; generated_by: string }>>([])

  // Auto-populate workspace path from title + dbxUser
  const safeTitle = title.replace(/[^a-zA-Z0-9]+/g, '_').slice(0, 60) || 'study'
  const defaultPath = `/Users/${dbxUser || 'me'}/ads_automation/${safeTitle}_attrition`

  useEffect(() => {
    if (!storedPath) setNotebookPath(defaultPath)
  }, [defaultPath, storedPath, setNotebookPath])

  const nbPath = storedPath || defaultPath

  // ── Build request ─────────────────────────────────────────────────────────
  const buildRequest = (): NotebookRequest => {
    const cleanSteps = steps.filter((s) => s.description.trim())

    const activeConds = new Set(selectedConds ?? allConds)
    const activeCodeLists = codeLists.filter((e) => activeConds.has(e.condition))

    // Group code entries into CodeListInput[]
    const grouped: Record<string, CodeListInput> = {}
    activeCodeLists.forEach((e) => {
      const key = `${e.condition}||${e.coding_system}`
      if (!grouped[key]) {
        grouped[key] = {
          condition: e.condition,
          coding_system: e.coding_system,
          codes: [],
          code_descriptions: [],
        }
      }
      grouped[key].codes.push(e.code)
      grouped[key].code_descriptions?.push(e.description)
    })

    const stepsInput: StepInput[] = cleanSteps.map((s, idx) => ({
      step_num: idx + 1,
      step_type: s.step_type,
      description: s.description,
      criterion_type: s.criterion_type,
    }))

    return {
      title,
      steps: stepsInput,
      code_lists: Object.values(grouped),
      study_window: studyWindow,
      workspace_path: nbPath,
    }
  }

  // ── Generate & Push ───────────────────────────────────────────────────────
  const handleGenerate = async () => {
    const cleanSteps = steps.filter((s) => s.description.trim())
    if (!cleanSteps.length) { setError('Add at least one attrition step.'); return }
    setError(null)
    setIsGenerating(true)
    try {
      const req = buildRequest()
      const res = await generateNotebook(req)
      setNotebookResult(res.notebook_sql, res.workspace_url ?? '', res.warnings)
      setStepSQLs(res.steps.map((s) => ({ step_num: s.step_num, generated_by: s.generated_by })))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setIsGenerating(false)
    }
  }

  // ── Download SQL ──────────────────────────────────────────────────────────
  const handleDownload = () => {
    if (notebookSql) downloadNotebookSql(title, notebookSql)
  }

  const cleanSteps = steps.filter((s) => s.description.trim())

  return (
    <>
      {/* Workspace path */}
      <div className="form-group">
        <label>Databricks workspace path</label>
        <input
          type="text"
          className="input-mono"
          value={nbPath}
          onChange={(e) => setNotebookPath(e.target.value)}
          placeholder="/Users/user@domain.com/ads_automation/study_attrition"
        />
        <div style={{ fontSize: '0.68rem', color: 'var(--jnj-gray-05)', marginTop: 4 }}>
          Full workspace path where the notebook will be saved. Must start with /Users/&lt;email&gt;/ or /Shared/.
        </div>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={isGenerating || !cleanSteps.length}
          style={{ flex: '2 1 220px' }}
        >
          {isGenerating ? (
            <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Generating…</>
          ) : (
            dbxConnected ? 'Generate & Push to Databricks' : 'Generate Notebook'
          )}
        </button>

        {notebookSql && (
          <button
            className="btn btn-secondary"
            onClick={handleDownload}
            style={{ flex: '1 1 130px' }}
          >
            ↓ Download SQL
          </button>
        )}
      </div>

      {!cleanSteps.length && (
        <div style={{ fontSize: '0.78rem', color: 'var(--jnj-gray-05)', marginBottom: '0.75rem' }}>
          Add at least one attrition step in Step 2 to enable generation.
        </div>
      )}

      {/* Error */}
      {error && <div className="banner banner-error">{error}</div>}

      {/* Success */}
      {notebookUrl && (
        <div className="banner banner-success">
          Notebook pushed to Databricks &nbsp;·&nbsp;
          {cleanSteps.length} steps &nbsp;·&nbsp;
          {codeLists.length} codes
          <br />
          <a href={notebookUrl} target="_blank" rel="noreferrer" style={{ color: '#1e5c0a', fontWeight: 700 }}>
            {nbPath} →
          </a>
        </div>
      )}

      {/* Fallback warnings */}
      {notebookWarnings.length > 0 && (
        <div className="banner banner-warning">
          <strong>LLM fallback used for:</strong>
          <ul style={{ margin: '0.4rem 0 0 1.2rem', fontSize: '0.8rem' }}>
            {notebookWarnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* Step preview */}
      {notebookSql && cleanSteps.length > 0 && (
        <div className="step-preview-list" style={{ marginTop: '1.25rem' }}>
          <div className="step-preview-header">
            Step Preview &nbsp;·&nbsp; {cleanSteps.length} steps
          </div>
          {cleanSteps.map((step, idx) => {
            const isInc = step.step_type === 'inclusion'
            const sqlMeta = stepSQLs.find((s) => s.step_num === idx + 1)
            return (
              <div className="step-row" key={step.id}>
                <span className="step-index">{(idx + 1).toString().padStart(2, '0')}</span>
                <span className={`type-badge ${isInc ? 'inc' : 'exc'}`}>
                  {isInc ? 'INC' : 'EXC'}
                </span>
                <span className="step-text">{step.description}</span>
                {sqlMeta && (
                  <span
                    style={{
                      fontSize: '0.58rem', fontFamily: "'Roboto Mono',monospace",
                      color: sqlMeta.generated_by === 'llm' ? 'var(--jnj-green-03)' : 'var(--jnj-orange)',
                      flexShrink: 0,
                    }}
                  >
                    {sqlMeta.generated_by}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Active code lists summary */}
      {codeLists.length > 0 && (
        <div style={{ marginTop: '1.25rem' }}>
          <div style={{
            fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: 'var(--jnj-gray-05)', marginBottom: '0.5rem',
          }}>
            Code Lists included in notebook
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {[...new Set(
              codeLists
                .filter((e) => (selectedConds ?? allConds).includes(e.condition))
                .map((e) => `${e.condition} · ${e.coding_system}`)
            )].map((label) => {
              const sys = label.split(' · ')[1]
              const style = CODING_SYSTEM_STYLE[sys as keyof typeof CODING_SYSTEM_STYLE]
              return (
                <span
                  key={label}
                  style={{
                    fontSize: '0.68rem', fontWeight: 600,
                    border: `1px solid ${style?.border ?? '#a39992'}`,
                    color: style?.border ?? '#a39992',
                    background: style?.bg ?? '#f5f4f2',
                    borderRadius: 5, padding: '2px 8px',
                  }}
                >
                  {label}
                </span>
              )
            })}
          </div>
        </div>
      )}
    </>
  )
}
