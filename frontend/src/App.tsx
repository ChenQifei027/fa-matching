import { useState } from 'react'
import TopNav from './components/TopNav'
import Projects from './pages/Projects'
import Institutions from './pages/Institutions'
import Matching from './pages/Matching'
import Settings from './pages/Settings'

type Page = 'projects' | 'institutions' | 'matching' | 'settings'

export default function App() {
  const [page, setPage] = useState<Page>('projects')
  const [matchProjectId, setMatchProjectId] = useState<number | null>(null)

  function goToMatch(pid: number) {
    setMatchProjectId(pid)
    setPage('matching')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <TopNav current={page} onNavigate={(p) => setPage(p as Page)} />
      <main style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
        {page === 'projects'     && <Projects onGoToMatch={goToMatch} />}
        {page === 'institutions' && <Institutions />}
        {page === 'matching'     && <Matching initialProjectId={matchProjectId} />}
        {page === 'settings'     && <Settings />}
      </main>
    </div>
  )
}
