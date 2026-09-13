/**
 * App root — persistent layout with sidebar + scrollable main.
 * All 4 workflow steps render on one page (matching Streamlit's single-page design).
 */
import { useEffect } from 'react'
import { NavBar }      from './components/layout/NavBar'
import { Sidebar }     from './components/layout/Sidebar'
import { HeroBand }    from './components/layout/HeroBand'
import { Footer }      from './components/layout/Footer'
import { Step1Input }  from './components/steps/Step1Input'
import { Step2Edit }   from './components/steps/Step2Edit'
import { Step3CodeLists } from './components/steps/Step3CodeLists'
import { Step4Generate }  from './components/steps/Step4Generate'
import { useStore }    from './store/useStore'
import { checkHealth } from './api/client'

export default function App() {
  const setDbxStatus = useStore((s) => s.setDbxStatus)

  // On mount: probe health endpoint to detect Databricks context
  useEffect(() => {
    checkHealth()
      .then((h) =>
        setDbxStatus(
          h.databricks_connected,
          h.user ?? '',
          h.is_databricks_app,
          h.notebook_workspace_root,
        ),
      )
      .catch(() => setDbxStatus(false, '', false))
  }, [setDbxStatus])

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <NavBar />
        <HeroBand />
        <div className="content">
          <Step1Input />
          <Step2Edit />
          <Step3CodeLists />
          <Step4Generate />
          <Footer />
        </div>
      </div>
    </div>
  )
}
