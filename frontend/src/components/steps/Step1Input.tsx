/**
 * Step 1 — Protocol Input.
 *
 * Three tabs:
 *   Upload — drag-and-drop DOCX/PDF → POST /api/protocol/upload
 *   Paste  — paste raw protocol text → POST /api/protocol/parse
 *   Manual — type title + data source → blank step table
 *
 * On success, all tabs populate the Zustand store with parsed steps.
 */
import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useStore, uid } from '../../store/useStore'
import { uploadProtocol, parseProtocolText } from '../../api/client'
import type { APIAttritionStep } from '../../types'

type Tab = 'upload' | 'paste' | 'manual'

function apiStepsToStore(steps: APIAttritionStep[]) {
  return steps.map((s) => ({
    id: uid(),
    step_type: s.step_type,
    description: s.description,
    criterion_type: s.criterion_type,
    raw_text: s.raw_text,
    step_num: s.step_num,
  }))
}

export function Step1Input() {
  const [tab, setTab]           = useState<Tab>('upload')
  const [error, setError]       = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  // Manual entry local state
  const [manualTitle, setManualTitle]   = useState('')
  const [manualSource, setManualSource] = useState('')

  // Paste tab local state
  const [pasteText, setPasteText] = useState('')

  const isParsing      = useStore((s) => s.isParsing)
  const setIsParsing   = useStore((s) => s.setIsParsing)
  const setParseResult = useStore((s) => s.setParseResult)

  // ── Upload handler ──────────────────────────────────────────────────────────
  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0]
      if (!file) return
      setError(null)
      setWarnings([])
      setIsParsing(true)
      try {
        const result = await uploadProtocol(file)
        setParseResult({
          title: result.title,
          dataSources: result.data_sources,
          studyWindow: result.study_window,
          steps: apiStepsToStore(result.all_steps),
          parseMethod: result.parse_method,
          parsedSummary: result.summary ?? '',
          warnings: result.warnings,
          inputMode: 'upload',
        })
        if (result.warnings.length) setWarnings(result.warnings)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Upload failed')
      } finally {
        setIsParsing(false)
      }
    },
    [setIsParsing, setParseResult],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'], 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isParsing,
  })

  // ── Paste handler ───────────────────────────────────────────────────────────
  const handlePaste = async () => {
    if (!pasteText.trim()) { setError('Paste some protocol text first.'); return }
    setError(null); setWarnings([])
    setIsParsing(true)
    try {
      const result = await parseProtocolText(pasteText)
      setParseResult({
        title: result.title,
        dataSources: result.data_sources,
        studyWindow: result.study_window,
        steps: apiStepsToStore(result.all_steps),
        parseMethod: result.parse_method,
        parsedSummary: result.summary ?? '',
        warnings: result.warnings,
        inputMode: 'text',
      })
      if (result.warnings.length) setWarnings(result.warnings)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Parse failed')
    } finally {
      setIsParsing(false)
    }
  }

  // ── Manual entry handler ────────────────────────────────────────────────────
  const handleManual = () => {
    if (!manualTitle.trim()) { setError('Enter a study title.'); return }
    setParseResult({
      title: manualTitle.trim(),
      dataSources: manualSource.trim() ? [manualSource.trim()] : [],
      studyWindow: '',
      steps: [{ id: uid(), step_type: 'inclusion', description: '' }],
      parseMethod: 'manual',
      parsedSummary: '',
      warnings: [],
      inputMode: 'manual',
    })
  }

  return (
    <section>
      <div className="section-header" style={{ marginTop: 0 }}>
        <div className="step-num">1</div>
        <div>
          <div className="section-title">Protocol Input</div>
          <span className="section-title-sub">Upload a DOCX/PDF, paste text, or enter study details manually</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="tab-list">
        {(['upload', 'paste', 'manual'] as Tab[]).map((t) => (
          <button
            key={t}
            className={`tab-btn ${tab === t ? 'active' : ''}`}
            onClick={() => { setTab(t); setError(null); setWarnings([]) }}
          >
            {t === 'upload' ? '  Upload Protocol  ' : t === 'paste' ? '  Paste Text  ' : '  Enter Manually  '}
          </button>
        ))}
      </div>

      {/* Error / Warnings */}
      {error && <div className="banner banner-error" style={{ marginBottom: '1rem' }}>{error}</div>}
      {warnings.map((w, i) => (
        <div key={i} className="banner banner-warning" style={{ marginBottom: '0.5rem' }}>{w}</div>
      ))}

      {/* ── Upload tab ── */}
      {tab === 'upload' && (
        <div>
          <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'drag-active' : ''}`}>
            <input {...getInputProps()} />
            <div className="upload-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            {isParsing ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
                <div className="spinner" />
                <span className="upload-text">Parsing protocol with AI…</span>
              </div>
            ) : (
              <>
                <div className="upload-text">
                  {isDragActive ? 'Drop the file here…' : 'Drag & drop a protocol file, or click to browse'}
                </div>
                <div className="upload-text-sub">Supports DOCX, PDF · LLM-based universal parsing</div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Paste tab ── */}
      {tab === 'paste' && (
        <div className="card">
          <div className="hints">
            <span className="hint">Paste the inclusion & exclusion criteria sections</span>
            <span className="hint">Claude extracts all criteria semantically — any format</span>
            <span className="hint">No fixed headings or stop words</span>
          </div>
          <div className="form-group">
            <label>Protocol Text</label>
            <textarea
              rows={12}
              placeholder="Paste the protocol text here — any section, any format (PDF extract, DOCX paste, etc.)…"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              style={{ resize: 'vertical', fontFamily: 'Inter, sans-serif', fontSize: '0.82rem', lineHeight: 1.6 }}
            />
          </div>
          <button
            className="btn btn-primary"
            onClick={handlePaste}
            disabled={isParsing || !pasteText.trim()}
          >
            {isParsing ? (
              <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Parsing…</>
            ) : (
              'Parse Protocol'
            )}
          </button>
        </div>
      )}

      {/* ── Manual tab ── */}
      {tab === 'manual' && (
        <div className="card">
          <div className="hints">
            <span className="hint">Type your study title below</span>
            <span className="hint">Add each attrition step in the table (Step 2)</span>
            <span className="hint">Choose Inclusion or Exclusion per row</span>
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label>Study Title *</label>
              <input
                type="text"
                placeholder="e.g. Comparative effectiveness of MMAE adjunct…"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Data Source (optional)</label>
              <input
                type="text"
                placeholder="e.g. Premier Healthcare Database"
                value={manualSource}
                onChange={(e) => setManualSource(e.target.value)}
              />
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleManual} disabled={!manualTitle.trim()}>
            Start Entering Steps
          </button>
        </div>
      )}
    </section>
  )
}
