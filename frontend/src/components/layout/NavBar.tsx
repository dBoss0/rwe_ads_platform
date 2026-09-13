/** Top navigation bar — J&J logo, platform tag, version. */
const LOGO_URL =
  'https://play-lh.googleusercontent.com/' +
  'goJEGZ2I1rekFkK_Os2Hq6tgG_Iz07Wy6CyW2ti-Tn-j9_SiFVfAoQ6qKZKRJT-O_znd4tgvOgWK_8uHxWcBOQ'

export function NavBar() {
  return (
    <nav className="nav">
      <div className="nav-inner">
        <div className="nav-logo-wrap">
          <img src={LOGO_URL} className="nav-logo-img" alt="J&J" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
          <div className="nav-logo-divider" />
          <div>
            <div className="nav-logo-text">MedTech</div>
            <span className="nav-logo-sub">Agentic AI Platform</span>
          </div>
        </div>
        <div className="nav-right">
          <span className="nav-tag">Code Automation</span>
          <span className="nav-version">v2.0.0</span>
        </div>
      </div>
    </nav>
  )
}
