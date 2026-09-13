/**
 * Step 2 — Edit Attrition Steps.
 *
 * Editable table:
 *   - step_type column: dropdown (inclusion | exclusion)
 *   - description column: text input (inline edit)
 *   - Add row button, delete button per row, move up/down
 *   - Live stat row (total / inclusion / exclusion)
 *   - Meta strip shows study title and data sources
 */
import { useStore, selInclusionCount, selExclusionCount, selTotalCount } from '../../store/useStore'

export function Step2Edit() {
  const steps      = useStore((s) => s.steps)
  const title      = useStore((s) => s.title)
  const sources    = useStore((s) => s.dataSources)
  const inputMode  = useStore((s) => s.inputMode)
  const parseMethod = useStore((s) => s.parseMethod)
  const summary    = useStore((s) => s.parsedSummary)

  const updateStep = useStore((s) => s.updateStep)
  const removeStep = useStore((s) => s.removeStep)
  const moveStep   = useStore((s) => s.moveStep)
  const addStep    = useStore((s) => s.addStep)

  const inc   = useStore(selInclusionCount)
  const exc   = useStore(selExclusionCount)
  const total = useStore(selTotalCount)

  if (!inputMode) {
    return (
      <section>
        <div className="section-header">
          <div className="step-num">2</div>
          <div>
            <div className="section-title">Edit Attrition Steps</div>
            <span className="section-title-sub">Add, remove, or modify any step — changes flow directly into the notebook</span>
          </div>
        </div>
        <div className="empty-state">Upload a protocol or enter steps manually in Step 1 to begin editing.</div>
      </section>
    )
  }

  const sourcesDisplay = sources.length ? sources.join(', ') : 'Not detected'
  const parseLabel: Record<string, string> = {
    llm_databricks:  'AI Functions (full pipeline)',
    llm_rest:        'Claude REST (text)',
    llm_rest_local:  'Claude REST (local DOCX)',
    llm_rest_text:   'Claude REST (pasted text)',
    manual:          'Manual entry',
    error:           'Error',
  }

  return (
    <section>
      <div className="section-header">
        <div className="step-num">2</div>
        <div>
          <div className="section-title">Edit Attrition Steps</div>
          <span className="section-title-sub">Add, remove, or modify any step — changes flow directly into the notebook</span>
        </div>
      </div>

      {/* Meta strip */}
      <div className="meta-strip">
        <div className="meta-item">
          <span className="meta-label">Study Title</span>
          <span className="meta-value">{title}</span>
        </div>
        <div className="meta-divider" />
        <div className="meta-item">
          <span className="meta-label">Data Source</span>
          <span className="meta-value">{sourcesDisplay}</span>
        </div>
        <div className="meta-divider" />
        <div className="meta-item">
          <span className="meta-label">Parse Method</span>
          <span className="meta-value" style={{ fontSize: '0.78rem', color: 'var(--jnj-gray-06)' }}>
            {parseLabel[parseMethod] ?? parseMethod}
          </span>
        </div>
      </div>

      {/* AI summary */}
      {summary && (
        <div className="banner banner-info" style={{ marginBottom: '1rem' }}>
          <strong style={{ fontSize: '0.65rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Protocol Summary</strong>
          <br />{summary}
        </div>
      )}

      {/* Hints */}
      <div className="hints">
        <span className="hint">Click any cell to edit text</span>
        <span className="hint">Dropdown → switch Inclusion / Exclusion</span>
        <span className="hint">↑↓ to reorder steps</span>
        <span className="hint">✕ to remove a step</span>
        <span className="hint">+ Add Step to append a row</span>
      </div>

      {/* Editable table */}
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th style={{ width: 140 }}>Type</th>
              <th>Step Description</th>
              <th style={{ width: 32 }} />
              <th style={{ width: 60 }} />
            </tr>
          </thead>
          <tbody>
            {steps.map((step, idx) => (
              <tr key={step.id}>
                <td>
                  <span style={{ fontFamily: "'Roboto Mono',monospace", fontSize: '0.65rem', color: 'var(--jnj-gray-05)' }}>
                    {(idx + 1).toString().padStart(2, '0')}
                  </span>
                </td>
                <td>
                  <select
                    value={step.step_type}
                    onChange={(e) => updateStep(step.id, 'step_type', e.target.value)}
                    style={{ width: 128 }}
                  >
                    <option value="inclusion">Inclusion</option>
                    <option value="exclusion">Exclusion</option>
                  </select>
                </td>
                <td>
                  <div className="step-desc-cell">
                    <input
                      type="text"
                      value={step.description}
                      placeholder="Describe this attrition step…"
                      onChange={(e) => updateStep(step.id, 'description', e.target.value)}
                      style={{ flex: 1 }}
                    />
                    {step.criterion_type && step.criterion_type !== 'other' && (
                      <span
                        style={{
                          fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.08em',
                          textTransform: 'uppercase', background: 'rgba(15,104,178,0.08)',
                          color: 'var(--jnj-blue-03)', border: '1px solid rgba(15,104,178,0.2)',
                          borderRadius: 4, padding: '2px 6px', whiteSpace: 'nowrap', flexShrink: 0,
                        }}
                      >
                        {step.criterion_type}
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  {/* Move up / down */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ padding: '1px 5px', fontSize: 10 }}
                      disabled={idx === 0}
                      onClick={() => moveStep(step.id, 'up')}
                      title="Move up"
                    >▲</button>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ padding: '1px 5px', fontSize: 10 }}
                      disabled={idx === steps.length - 1}
                      onClick={() => moveStep(step.id, 'down')}
                      title="Move down"
                    >▼</button>
                  </div>
                </td>
                <td>
                  <button
                    className="btn btn-danger btn-sm"
                    style={{ padding: '3px 8px' }}
                    onClick={() => removeStep(step.id)}
                    title="Remove step"
                  >✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add row */}
      <div style={{ marginTop: '0.75rem' }}>
        <button className="btn btn-secondary btn-sm" onClick={addStep}>+ Add Step</button>
      </div>

      {/* Live stat row */}
      <div className="stat-row">
        <div className="stat-cell">
          <span className="stat-cell-label">Total Steps</span>
          <span className="stat-cell-value">{total}</span>
        </div>
        <div className="stat-cell">
          <span className="stat-cell-label">Inclusion</span>
          <span className="stat-cell-value blue">{inc}</span>
        </div>
        <div className="stat-cell">
          <span className="stat-cell-label">Exclusion</span>
          <span className="stat-cell-value red">{exc}</span>
        </div>
      </div>
    </section>
  )
}
