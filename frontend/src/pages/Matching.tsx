import { useState, useEffect } from 'react'
import { projectsApi, Project } from '../api/projects'
import { institutionsApi, Institution } from '../api/institutions'
import { matchingApi, MatchResult } from '../api/matching'
import Badge from '../components/Badge'
import Spinner from '../components/Spinner'

type Tab = 'p2i'|'i2p'

export default function Matching({ initialProjectId }: { initialProjectId: number|null }) {
  const [tab, setTab] = useState<Tab>('p2i')
  const [projects, setProjects] = useState<Project[]>([])
  const [institutions, setInstitutions] = useState<Institution[]>([])
  const [selectedPid, setSelectedPid] = useState<number|null>(initialProjectId)
  const [selectedIid, setSelectedIid] = useState<number|null>(null)
  const [results, setResults] = useState<MatchResult[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(()=>{ projectsApi.list().then(setProjects); institutionsApi.list().then(setInstitutions) },[])
  useEffect(()=>{ if(initialProjectId){ setSelectedPid(initialProjectId); setTab('p2i') } },[initialProjectId])

  async function runMatch() {
    setLoading(true); setResults([])
    try {
      if(tab==='p2i' && selectedPid) setResults(await matchingApi.projectToInstitutions(selectedPid))
      else if(tab==='i2p' && selectedIid) setResults(await matchingApi.institutionToProjects(selectedIid))
    } finally { setLoading(false) }
  }

  const items = tab==='p2i' ? projects : institutions
  const selectedId = tab==='p2i' ? selectedPid : selectedIid
  const setSelected = (id: number) => tab==='p2i' ? setSelectedPid(id) : setSelectedIid(id)

  return (
    <div>
      <h1 style={{ fontSize:18, fontWeight:600, marginBottom:20 }}>匹配推荐</h1>
      <div style={{ display:'flex', borderBottom:'1px solid var(--border)', marginBottom:20 }}>
        {(['p2i','i2p'] as Tab[]).map(t=>(
          <button key={t} onClick={()=>{setTab(t);setResults([])}} style={{ padding:'8px 16px', background:'none', border:'none', cursor:'pointer', color:tab===t?'var(--text-primary)':'var(--text-secondary)', borderBottom:`2px solid ${tab===t?'var(--accent)':'transparent'}`, marginBottom:-1, fontSize:13 }}>
            {t==='p2i'?'项目 → 推荐机构':'机构 → 推荐项目'}
          </button>
        ))}
      </div>
      <div style={{ display:'flex', gap:24 }}>
        <div style={{ width:220, flexShrink:0 }}>
          <div style={{ color:'var(--text-muted)', fontSize:11, textTransform:'uppercase', letterSpacing:.5, marginBottom:8 }}>{tab==='p2i'?'选择项目':'选择机构'}</div>
          {items.map(item=>{
            const isSel = selectedId===item.id
            return (
              <div key={item.id} onClick={()=>setSelected(item.id)} style={{ background:isSel?'var(--bg-elevated)':'var(--bg-surface)', border:`1px solid ${isSel?'var(--accent)':'var(--border)'}`, borderRadius:6, padding:'10px 12px', marginBottom:6, cursor:'pointer' }}>
                <div style={{ color:isSel?'#fff':'var(--text-secondary)', fontSize:13 }}>{item.name}</div>
              </div>
            )
          })}
          <button onClick={runMatch} disabled={loading||!selectedId} style={{ width:'100%', marginTop:8, background:'linear-gradient(135deg,var(--accent),var(--accent-light))', color:'#fff', border:'none', borderRadius:6, padding:'9px 16px', fontWeight:500, fontSize:13, opacity:!selectedId?.5:1 }}>
            {loading?'匹配中…':'🚀 开始匹配'}
          </button>
        </div>
        <div style={{ flex:1 }}>
          {loading && <div style={{ display:'flex', alignItems:'center', gap:8, color:'var(--text-secondary)', padding:16 }}><Spinner/> LLM 分析中，约 20–60 秒…</div>}
          {!loading && results.length===0 && <div style={{ color:'var(--text-muted)', padding:16 }}>{selectedId?'点击「开始匹配」获取推荐':'请先从左侧选择'}</div>}
          {results.map((r,i)=>(
            <div key={i} style={{ background:'var(--bg-surface)', border:'1px solid var(--border)', borderRadius:8, padding:16, marginBottom:10 }}>
              <div style={{ display:'flex', alignItems:'flex-start', marginBottom:6 }}>
                <span style={{ flex:1, fontSize:14, fontWeight:600, color:'#fff' }}>{r.name}</span>
                <span style={{ background:'linear-gradient(135deg,var(--accent),var(--accent-light))', color:'#fff', fontWeight:700, fontSize:14, borderRadius:6, padding:'3px 10px' }}>{r.score}</span>
              </div>
              <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:8 }}>
                {(r.preferred_sectors||'').split(',').filter(Boolean).slice(0,3).map(s=><Badge key={s} variant="blue">{s.trim()}</Badge>)}
                {(r.preferred_stages||'').split(',').filter(Boolean).slice(0,2).map(s=><Badge key={s} variant="amber">{s.trim()}</Badge>)}
              </div>
              <p style={{ color:'var(--text-secondary)', fontSize:12, lineHeight:1.6 }}>{r.reason}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
