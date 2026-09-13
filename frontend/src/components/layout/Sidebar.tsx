/**
 * Sidebar — New Protocol button, step summary, Databricks connection status,
 * last output path, one-time setup.
 */
import { useState } from 'react'
import {
  useStore,
  selInclusionCount,
  selExclusionCount,
  selTotalCount,
} from '../../store/useStore'
import { JnJLogo } from '../ui/JnJLogo'

const LOGO_URL =
  'https://play-lh.googleusercontent.com/' +
  'goJEGZ2I1rekFkK_Os2Hq6tgG_Iz07Wy6CyW2ti-Tn-j9_SiFVfAoQ6qKZKRJT-O_znd4tgvOgWK_8uHxWcBOQ'

export function Sidebar() {
  const [logoFailed, setLogoFailed] = useState(false)
  const resetProtocol  = useStore((s) => s.resetProtocol)
  const steps          = useStore((s) => s.steps)
  const notebookPath   = useStore((s) => s.notebookPath)
  const notebookUrl    = useStore((s) => s.notebookUrl)
  const dbxConnected   = useStore((s) => s.dbxConnected)
  const dbxUser        = useStore((s) => s.dbxUser)
  const dbxIsApp       = useStore((s) => s.dbxIsDatabricksApp)
  const hasSteps       = steps.length > 0

  const inc   = useStore(selInclusionCount)
  const exc   = useStore(selExclusionCount)
  const total = useStore(selTotalCount)

  return (
    <aside className="app-sidebar">
      <div className="sidebar-content">
        {/* Brand */}
        <div className="sidebar-brand">
          {logoFailed ? (
            <JnJLogo height={34} variant="icon" />
          ) : (
            <img
              src={LOGO_URL}
              style={{ height: 36, width: 'auto', marginBottom: 8, display: 'block' }}
              alt="Johnson & Johnson"
              onError={() => setLogoFailed(true)}
            />
          )}
          <div className="sidebar-brand-name">Code Automation</div>
          <div className="sidebar-brand-sub">Protocol Intelligence Platform</div>
        </div>

        {/* New Protocol */}
        <button className="btn btn-secondary btn-full" onClick={resetProtocol}>
          New Protocol
        </button>

        {/* Step summary */}
        {hasSteps && (
          <>
            <div className="sidebar-section-label">Step Summary</div>
            <div className="sidebar-stat total">
              <span>Total Steps</span>
              <span className="sidebar-stat-num">{total}</span>
            </div>
            <div className="sidebar-stat inc">
              <span>Inclusion</span>
              <span className="sidebar-stat-num">{inc}</span>
            </div>
            <div className="sidebar-stat exc">
              <span>Exclusion</span>
              <span className="sidebar-stat-num">{exc}</span>
            </div>
          </>
        )}

        {/* Last output */}
        {notebookPath && (
          <>
            <div className="sidebar-divider" />
            <div className="sidebar-section-label">Last Output</div>
            <div className="sidebar-output">{notebookPath}</div>
          </>
        )}

        {/* Databricks connection */}
        <div className="sidebar-divider" />
        <div className="sidebar-section-label">Databricks Connection</div>
        {dbxIsApp ? (
          <div className="sidebar-dbx-ok">Connected via Databricks App</div>
        ) : dbxConnected ? (
          <div className="sidebar-dbx-ok">Connected · {dbxUser}</div>
        ) : (
          <div
            style={{
              fontSize: '0.72rem',
              color: 'var(--jnj-gray-05)',
              lineHeight: 1.5,
              padding: '0.4rem 0',
            }}
          >
            Not connected — deploy to Databricks to enable full pipeline.
          </div>
        )}

        {/* Open notebook link */}
        {notebookUrl && (
          <a
            href={notebookUrl}
            target="_blank"
            rel="noreferrer"
            className="sidebar-output"
            style={{ color: 'var(--jnj-green-03)', display: 'block', marginTop: 8 }}
          >
            Open in Databricks →
          </a>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Footer tip */}
        <div
          style={{
            fontSize: '0.6rem',
            color: 'var(--jnj-gray-05)',
            paddingTop: '1rem',
            borderTop: '1px solid var(--jnj-gray-02)',
            lineHeight: 1.5,
          }}
        >
          Agentic AI Platform · Internal Use Only
        </div>
      </div>
    </aside>
  )
}
