/**
 * Parse pipeline status indicator — shows which of the 5 AI stages ran.
 * Displayed after protocol parsing to build trust in the AI output.
 */
interface PipelineStatusProps {
  parseMethod: string
  warnings: string[]
  summary?: string
}

const STAGES = [
  { key: 'doc',      label: 'Document Extract',     desc: 'ai_parse_document',   databricksOnly: true },
  { key: 'extract',  label: 'Field Extraction',      desc: 'ai_extract v2.1',     databricksOnly: true },
  { key: 'claude',   label: 'Criteria Extraction',   desc: 'Claude REST',         databricksOnly: false },
  { key: 'classify', label: 'Type Classification',   desc: 'ai_classify_batch',   databricksOnly: true },
  { key: 'summarize',label: 'Protocol Summary',      desc: 'ai_summarize',        databricksOnly: true },
]

export function PipelineStatus({ parseMethod, warnings }: PipelineStatusProps) {
  const isDatabricks = parseMethod === 'llm_databricks'

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #0f1923 0%, #162032 100%)',
        border: '1px solid rgba(105,208,255,0.15)',
        borderRadius: 12,
        padding: '1.1rem 1.4rem',
        marginBottom: '1.25rem',
      }}
    >
      <div
        style={{
          fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.2em',
          textTransform: 'uppercase', color: '#69d0ff', marginBottom: '0.85rem',
        }}
      >
        AI Parse Pipeline
      </div>
      <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
        {STAGES.map((stage, idx) => {
          const ran = isDatabricks || (!stage.databricksOnly)
          const isGate = stage.key === 'claude'

          return (
            <div key={stage.key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {idx > 0 && (
                <div style={{ width: 20, height: 1, background: ran ? 'rgba(105,208,255,0.3)' : 'rgba(255,255,255,0.1)' }} />
              )}
              <div
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  gap: 3, minWidth: 80,
                }}
              >
                <div
                  style={{
                    width: 28, height: 28, borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, fontWeight: 700,
                    background: ran
                      ? isGate
                        ? 'rgba(235,23,0,0.3)'
                        : 'rgba(50,135,20,0.25)'
                      : 'rgba(255,255,255,0.05)',
                    border: `2px solid ${ran ? (isGate ? '#eb1700' : '#328714') : 'rgba(255,255,255,0.1)'}`,
                    color: ran ? (isGate ? '#ff6b6b' : '#6dd67f') : 'rgba(255,255,255,0.2)',
                  }}
                >
                  {ran ? '✓' : '—'}
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '0.6rem', fontWeight: 700, color: ran ? '#ffffff' : 'rgba(255,255,255,0.2)', whiteSpace: 'nowrap' }}>
                    {stage.label}
                  </div>
                  <div style={{ fontSize: '0.5rem', color: ran ? '#69d0ff' : 'rgba(255,255,255,0.1)', fontFamily: "'Roboto Mono',monospace", whiteSpace: 'nowrap' }}>
                    {stage.desc}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
      {!isDatabricks && (
        <div style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.4)', marginTop: '0.75rem' }}>
          Stages 1, 2, 4, 5 require Databricks deployment · Stage 3 (Claude) always runs
        </div>
      )}
      {warnings.length > 0 && (
        <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {warnings.map((w, i) => (
            <div key={i} style={{ fontSize: '0.65rem', color: '#ff9f43', display: 'flex', gap: 6 }}>
              <span>⚠</span><span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
