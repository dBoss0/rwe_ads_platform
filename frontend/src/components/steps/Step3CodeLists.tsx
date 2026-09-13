/**
 * Step 3 — Code Lists.
 *
 * Two tabs:
 *   Manual Entry  — condition name + coding system dropdown + codes textarea
 *   Upload Excel  — multi-file upload, per-sheet column mapping with auto-detection
 *
 * Displays existing code lists grouped by condition with system-colored badges,
 * expandable code viewer, delete per group, and procedure category multiselect.
 */
import { useState, useCallback, useRef } from 'react'
import * as XLSX from 'xlsx'
import { useDropzone } from 'react-dropzone'
import {
  useStore,
  selAllConditions,
} from '../../store/useStore'
import {
  CODING_SYSTEMS,
  CODING_SYSTEM_STYLE,
  type CodingSystem,
} from '../../types'

// ── helpers ──────────────────────────────────────────────────────────────────
function parseCodes(raw: string): string[] {
  return raw
    .split(/[\n,;\t]+/)
    .map((p) => p.trim().toUpperCase())
    .filter(Boolean)
}

function makeTmpName(condition: string, system: string): string {
  const cond = condition.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  const sys  = system.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  return `tmp__${cond}__${sys}`
}

function guessCodingSystem(sheetName: string, sampleCodes: string[]): CodingSystem | null {
  const n = sheetName.toLowerCase()
  if (n.includes('icd-10') || n.includes('icd10')) return n.includes('pcs') ? 'ICD-10 PCS' : 'ICD-10 CM'
  if (n.includes('icd-9')  || n.includes('icd9'))  return n.includes('pcs') ? 'ICD-9 PCS'  : 'ICD-9 CM'
  if (n.includes('cpt'))    return 'CPT-4'
  if (n.includes('hcpcs'))  return 'HCPCS'
  if (n.includes('drg'))    return 'DRG'
  if (n.includes('ndc'))    return 'NDC'
  // Pattern detect
  const icd10 = /^[A-Z]\d{2}/i
  const ndc   = /^\d{10,11}$/
  if (sampleCodes.length) {
    const n = sampleCodes.length
    if (sampleCodes.filter((c) => icd10.test(c)).length / n > 0.6) return 'ICD-10 CM'
    if (sampleCodes.filter((c) => ndc.test(c)).length / n > 0.6)   return 'NDC'
  }
  return null
}

// ── Sheet mapping state ───────────────────────────────────────────────────────
interface SheetMapping {
  codeCol:     string
  descCol:     string
  condCol:     string
  condManual:  string
  sysCol:      string
  sysManual:   CodingSystem
}

interface ParsedSheet {
  name: string
  rows: Record<string, string>[]
  columns: string[]
  sampleCodes: string[]
  guessedSys: CodingSystem | null
}

// ── Main component ────────────────────────────────────────────────────────────
export function Step3CodeLists() {
  const inputMode = useStore((s) => s.inputMode)
  if (!inputMode) return null          // only show after Step 1 completed

  return (
    <section>
      <div className="section-header">
        <div className="step-num">3</div>
        <div>
          <div className="section-title">Code Lists</div>
          <span className="section-title-sub">
            Define ICD-9/10, CPT, HCPCS, DRG and NDC codes grouped by condition — feeds SQL generation
          </span>
        </div>
      </div>
      <CodeListsBody />
    </section>
  )
}

function CodeListsBody() {
  const [tab, setTab] = useState<'manual' | 'excel'>('manual')

  return (
    <>
      <div className="tab-list">
        <button className={`tab-btn ${tab === 'manual' ? 'active' : ''}`} onClick={() => setTab('manual')}>
          Manual Entry
        </button>
        <button className={`tab-btn ${tab === 'excel' ? 'active' : ''}`} onClick={() => setTab('excel')}>
          Upload Excel
        </button>
      </div>
      {tab === 'manual' ? <ManualEntry /> : <ExcelUpload />}
      <ExistingCodeLists />
    </>
  )
}

// ── Manual Entry ──────────────────────────────────────────────────────────────
function ManualEntry() {
  const addCodeEntries = useStore((s) => s.addCodeEntries)
  const [condition, setCondition] = useState('')
  const [system, setSystem]       = useState<CodingSystem>('ICD-10 CM')
  const [rawCodes, setRawCodes]   = useState('')
  const [error, setError]         = useState<string | null>(null)
  const [success, setSuccess]     = useState<string | null>(null)

  const handleAdd = () => {
    if (!condition.trim()) { setError('Enter a condition name.'); return }
    const codes = parseCodes(rawCodes)
    if (!codes.length) { setError('Enter at least one code.'); return }
    setError(null)

    addCodeEntries(codes.map((code) => ({
      condition: condition.trim(),
      coding_system: system,
      code,
      description: '',
    })))
    setSuccess(`${codes.length} codes added under "${condition.trim()}" (${system})`)
    setCondition(''); setRawCodes('')
    setTimeout(() => setSuccess(null), 3000)
  }

  return (
    <div className="card">
      <div className="hints">
        <span className="hint">One code group = one condition + one coding system</span>
        <span className="hint">Paste codes — comma, newline, or semicolon separated</span>
        <span className="hint">Add as many groups as needed</span>
      </div>
      {error   && <div className="banner banner-error" style={{ marginBottom: '0.75rem' }}>{error}</div>}
      {success && <div className="banner banner-success" style={{ marginBottom: '0.75rem' }}>{success}</div>}
      <div className="grid-2">
        <div className="form-group">
          <label>Condition / Concept Name</label>
          <input
            type="text"
            placeholder="e.g. Malnutrition, NSCLC, Chemotherapy"
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Coding System</label>
          <select value={system} onChange={(e) => setSystem(e.target.value as CodingSystem)}>
            {CODING_SYSTEMS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="form-group">
        <label>Codes</label>
        <textarea
          rows={6}
          placeholder="Paste codes here — one per line or comma separated&#10;E40&#10;E41&#10;E42"
          value={rawCodes}
          onChange={(e) => setRawCodes(e.target.value)}
          style={{ fontFamily: "'Roboto Mono',monospace", fontSize: '0.78rem', resize: 'vertical' }}
        />
      </div>
      <button className="btn btn-primary" onClick={handleAdd}>+ Add Code Group</button>
    </div>
  )
}

// ── Excel Upload ──────────────────────────────────────────────────────────────
const NOT_IN_SHEET = '— not in this sheet —'

function ExcelUpload() {
  const addCodeEntries = useStore((s) => s.addCodeEntries)
  const [sheets, setSheets]     = useState<ParsedSheet[]>([])
  const [mappings, setMappings] = useState<Record<string, SheetMapping>>({})
  const [messages, setMessages] = useState<Record<string, string>>({})   // success per sheet
  const fileRef = useRef<HTMLInputElement>(null)

  const onDrop = useCallback((files: File[]) => {
    setSheets([]); setMappings({}); setMessages({})
    files.forEach((file) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const data = new Uint8Array(e.target!.result as ArrayBuffer)
        const wb   = XLSX.read(data, { type: 'array' })

        const newSheets: ParsedSheet[] = wb.SheetNames.map((name) => {
          const ws   = wb.Sheets[name]
          const rows = XLSX.utils.sheet_to_json(ws, { defval: '' }) as Record<string, string>[]
          const cols = rows.length ? Object.keys(rows[0]) : []
          const sample = rows.slice(0, 20).map((r) => String(r[cols[0]] ?? '')).filter(Boolean)
          const guessedSys = guessCodingSystem(name, sample)
          return { name, rows, columns: cols, sampleCodes: sample, guessedSys }
        })

        setSheets((prev) => [...prev, ...newSheets])
        const initMappings: Record<string, SheetMapping> = {}
        newSheets.forEach((s) => {
          initMappings[s.name] = {
            codeCol:    NOT_IN_SHEET,
            descCol:    NOT_IN_SHEET,
            condCol:    NOT_IN_SHEET,
            condManual: '',
            sysCol:     NOT_IN_SHEET,
            sysManual:  s.guessedSys ?? 'ICD-10 CM',
          }
        })
        setMappings((prev) => ({ ...prev, ...initMappings }))
      }
      reader.readAsArrayBuffer(file)
    })
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
    },
    multiple: true,
  })

  const updateMapping = (sheet: string, field: keyof SheetMapping, val: string) => {
    setMappings((prev) => ({ ...prev, [sheet]: { ...prev[sheet], [field]: val } }))
  }

  const handleImport = (sheet: ParsedSheet) => {
    const m = mappings[sheet.name]
    if (!m || m.codeCol === NOT_IN_SHEET) return

    const rows = sheet.rows.filter((r) => String(r[m.codeCol] ?? '').trim())
    const entries = rows.map((row) => {
      const condition = m.condCol !== NOT_IN_SHEET
        ? String(row[m.condCol] ?? '').trim() || (m.condManual || sheet.name)
        : (m.condManual.trim() || sheet.name)

      const coding_system: CodingSystem = m.sysCol !== NOT_IN_SHEET
        ? (String(row[m.sysCol] ?? '').trim() as CodingSystem || m.sysManual)
        : m.sysManual

      return {
        condition,
        coding_system,
        code: String(row[m.codeCol]).trim().toUpperCase(),
        description: m.descCol !== NOT_IN_SHEET ? String(row[m.descCol] ?? '').trim() : '',
      }
    })

    addCodeEntries(entries)
    setMessages((prev) => ({
      ...prev,
      [sheet.name]: `${entries.length} codes imported from "${sheet.name}" (${[...new Set(entries.map((e) => e.condition))].length} condition(s))`,
    }))
  }

  return (
    <div className="card">
      <div className="hints">
        <span className="hint">Upload one or multiple Excel / CSV files</span>
        <span className="hint">Select a file, then configure each sheet</span>
        <span className="hint">You confirm every column mapping — no assumptions</span>
      </div>

      <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'drag-active' : ''}`} style={{ padding: '1.25rem' }}>
        <input {...getInputProps()} ref={fileRef} />
        <div className="upload-text" style={{ fontSize: '0.82rem' }}>
          {isDragActive ? 'Drop files here…' : 'Drag Excel / CSV files, or click to browse'}
        </div>
        <div className="upload-text-sub">.xlsx · .xls · .csv · multiple files supported</div>
      </div>

      {sheets.map((sheet) => {
        const m = mappings[sheet.name]
        if (!m) return null
        const colOptions = [NOT_IN_SHEET, ...sheet.columns]

        return (
          <SheetMapper
            key={sheet.name}
            sheet={sheet}
            m={m}
            colOptions={colOptions}
            updateMapping={updateMapping}
            onImport={() => handleImport(sheet)}
            successMsg={messages[sheet.name]}
          />
        )
      })}
    </div>
  )
}

interface SheetMapperProps {
  sheet: ParsedSheet
  m: SheetMapping
  colOptions: string[]
  updateMapping: (s: string, f: keyof SheetMapping, v: string) => void
  onImport: () => void
  successMsg?: string
}

function SheetMapper({ sheet, m, colOptions, updateMapping, onImport, successMsg }: SheetMapperProps) {
  const [open, setOpen] = useState(true)

  const label = [
    `Sheet: ${sheet.name}`,
    `${sheet.rows.length} rows`,
    sheet.guessedSys ? `Auto-detected: ${sheet.guessedSys}` : '',
  ].filter(Boolean).join('  ·  ')

  return (
    <div style={{ border: '1px solid var(--jnj-gray-02)', borderRadius: 8, marginTop: 12, overflow: 'hidden' }}>
      <button
        style={{
          width: '100%', background: 'var(--jnj-gray-01)', border: 'none', cursor: 'pointer',
          padding: '0.65rem 1rem', textAlign: 'left', display: 'flex', justifyContent: 'space-between',
          fontSize: '0.78rem', fontWeight: 600, color: 'var(--jnj-gray-08)',
        }}
        onClick={() => setOpen((o) => !o)}
      >
        {label}
        <span style={{ color: 'var(--jnj-gray-05)' }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={{ padding: '1rem' }}>
          {/* Sample rows */}
          <div style={{ overflowX: 'auto', marginBottom: '0.75rem' }}>
            <table className="data-table" style={{ fontSize: '0.72rem' }}>
              <thead>
                <tr>{sheet.columns.map((c) => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {sheet.rows.slice(0, 3).map((r, i) => (
                  <tr key={i}>{sheet.columns.map((c) => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>

          {successMsg && (
            <div className="banner banner-success" style={{ marginBottom: '0.75rem' }}>{successMsg}</div>
          )}

          <div className="grid-2">
            <div>
              <div className="form-group">
                <label>Code column *</label>
                <select value={m.codeCol} onChange={(e) => updateMapping(sheet.name, 'codeCol', e.target.value)}>
                  {colOptions.map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Description column (optional)</label>
                <select value={m.descCol} onChange={(e) => updateMapping(sheet.name, 'descCol', e.target.value)}>
                  {colOptions.map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
            </div>
            <div>
              <div className="form-group">
                <label>Condition column (if in file)</label>
                <select value={m.condCol} onChange={(e) => updateMapping(sheet.name, 'condCol', e.target.value)}>
                  {colOptions.map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>— or type condition name</label>
                <input
                  type="text"
                  placeholder="e.g. TKA"
                  value={m.condManual}
                  onChange={(e) => updateMapping(sheet.name, 'condManual', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Coding system column (if mixed)</label>
                <select value={m.sysCol} onChange={(e) => updateMapping(sheet.name, 'sysCol', e.target.value)}>
                  {colOptions.map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>— or select one coding system for all rows</label>
                <select value={m.sysManual} onChange={(e) => updateMapping(sheet.name, 'sysManual', e.target.value as CodingSystem)}>
                  {CODING_SYSTEMS.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
            </div>
          </div>

          <button
            className="btn btn-primary btn-sm"
            onClick={onImport}
            disabled={m.codeCol === NOT_IN_SHEET}
          >
            Import — {sheet.name}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Existing code lists display ────────────────────────────────────────────────
function ExistingCodeLists() {
  const codeLists          = useStore((s) => s.codeLists)
  const selectedConditions = useStore((s) => s.selectedConditions)
  const allConditions      = useStore(selAllConditions)
  const setSelectedConditions = useStore((s) => s.setSelectedConditions)
  const removeCodeGroup    = useStore((s) => s.removeCodeGroup)
  const clearCodeLists     = useStore((s) => s.clearCodeLists)

  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  if (!codeLists.length) return null

  const toggleExpand = (key: string) => setExpanded((p) => ({ ...p, [key]: !p[key] }))

  const totalCodes    = codeLists.length
  const totalConds    = allConditions.length
  const totalSystems  = new Set(codeLists.map((e) => e.coding_system)).size

  return (
    <div style={{ marginTop: '1.75rem' }}>
      {/* Summary line */}
      <div style={{
        fontSize: '0.65rem', fontWeight: 800, letterSpacing: '0.15em',
        textTransform: 'uppercase', color: 'var(--jnj-gray-05)', marginBottom: '0.75rem',
      }}>
        {totalCodes} codes &nbsp;·&nbsp; {totalConds} conditions &nbsp;·&nbsp; {totalSystems} coding systems
      </div>

      {/* Grouped by condition */}
      {allConditions.map((cond) => {
        const condEntries = codeLists.filter((e) => e.condition === cond)
        const systems = [...new Set(condEntries.map((e) => e.coding_system))]

        const badges = systems.map((sys) => {
          const count   = condEntries.filter((e) => e.coding_system === sys).length
          const style   = CODING_SYSTEM_STYLE[sys] ?? { border: '#a39992', bg: '#f5f4f2' }
          const tmp     = makeTmpName(cond, sys)
          const key     = `${cond}__${sys}`

          return (
            <span key={sys}>
              <span
                className="cl-sys-badge"
                style={{ borderColor: style.border, color: style.border, background: style.bg }}
                onClick={() => toggleExpand(key)}
                title="Click to view codes"
              >
                <span className="cl-sys-name">{sys}</span>
                <span className="cl-sys-count">&nbsp;{count} codes</span>
                <span className="cl-sys-tmp">{tmp}</span>
              </span>
              {expanded[key] && (
                <div className="accordion-panel">
                  {condEntries
                    .filter((e) => e.coding_system === sys)
                    .map((e) => e.code)
                    .slice(0, 60)
                    .join('   ·   ')}
                  {condEntries.filter((e) => e.coding_system === sys).length > 60 &&
                    `   … +${condEntries.filter((e) => e.coding_system === sys).length - 60} more`}
                  <div style={{ marginTop: 8 }}>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => removeCodeGroup(cond, sys)}
                    >
                      Delete group
                    </button>
                  </div>
                </div>
              )}
            </span>
          )
        })

        return (
          <div className="cl-condition-card" key={cond}>
            <div className="cl-condition-header">
              <span className="cl-condition-name">{cond}</span>
              <span className="cl-condition-total">{condEntries.length} codes total</span>
            </div>
            <div className="cl-badges-row">{badges}</div>
          </div>
        )
      })}

      {/* Clear all */}
      <button className="btn btn-secondary btn-sm" onClick={clearCodeLists} style={{ marginBottom: '1.25rem' }}>
        Clear All Code Lists
      </button>

      {/* Procedure category selector */}
      <div>
        <div style={{ fontSize: '0.65rem', fontWeight: 800, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--jnj-gray-05)', marginBottom: '0.4rem' }}>
          Procedure Categories for Notebook Generation
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--jnj-gray-06)', marginBottom: '0.5rem' }}>
          Only selected categories will create temp tables and appear in Step 1 SQL
        </div>
        <ConditionMultiSelect
          all={allConditions}
          selected={[...(selectedConditions ?? allConditions)]}
          onChange={(sel) => setSelectedConditions(sel.length === allConditions.length ? null : sel)}
        />
        {(() => {
          const sel = selectedConditions ?? allConditions
          const excl = allConditions.filter((c) => !sel.includes(c))
          return excl.length ? (
            <div style={{ fontSize: '0.72rem', color: 'var(--jnj-orange)', marginTop: '0.35rem' }}>
              {excl.length} category excluded from notebook: {excl.join(', ')}
            </div>
          ) : (
            <div style={{ fontSize: '0.72rem', color: 'var(--jnj-green-03)', marginTop: '0.35rem' }}>
              All {allConditions.length} categories selected.
            </div>
          )
        })()}
      </div>
    </div>
  )
}

// ── Condition multiselect ──────────────────────────────────────────────────────
function ConditionMultiSelect({
  all, selected, onChange,
}: { all: string[]; selected: string[]; onChange: (v: string[]) => void }) {
  const selSet = new Set(selected)

  const toggle = (cond: string) => {
    if (selSet.has(cond)) {
      onChange(selected.filter((c) => c !== cond))
    } else {
      onChange([...selected, cond])
    }
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
      {all.map((cond) => {
        const active = selSet.has(cond)
        return (
          <button
            key={cond}
            className="btn btn-sm"
            style={{
              background: active ? 'rgba(15,104,178,0.1)' : '#fff',
              color: active ? 'var(--jnj-blue-03)' : 'var(--jnj-gray-06)',
              border: `1px solid ${active ? 'rgba(15,104,178,0.25)' : 'var(--jnj-gray-03)'}`,
              fontWeight: active ? 700 : 500,
            }}
            onClick={() => toggle(cond)}
          >
            {active ? '✓ ' : ''}{cond}
          </button>
        )
      })}
    </div>
  )
}
