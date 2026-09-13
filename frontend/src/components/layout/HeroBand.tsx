/** Hero band — dark gradient, title, live stats. */
import {
  useStore,
  selInclusionCount,
  selExclusionCount,
  selTotalCount,
} from '../../store/useStore'

export function HeroBand() {
  const inc   = useStore(selInclusionCount)
  const exc   = useStore(selExclusionCount)
  const total = useStore(selTotalCount)

  return (
    <div className="hero">
      <div className="hero-inner">
        <div className="hero-eyebrow">J&amp;J MedTech &nbsp;·&nbsp; Agentic AI Platform</div>
        <div className="hero-title">
          Code <span>Automation</span>
        </div>
        <div className="hero-stats">
          <div>
            <div className="hero-stat-num">{total}<span>.</span></div>
            <div className="hero-stat-label">Total Steps</div>
          </div>
          <div>
            <div className="hero-stat-num">{inc}<span>.</span></div>
            <div className="hero-stat-label">Inclusion</div>
          </div>
          <div>
            <div className="hero-stat-num">{exc}<span>.</span></div>
            <div className="hero-stat-label">Exclusion</div>
          </div>
        </div>
      </div>
    </div>
  )
}
