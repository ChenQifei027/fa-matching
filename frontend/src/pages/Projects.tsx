import { useState, useEffect, useCallback } from 'react'
import SectorDrawer, { ClickableSectorBadge } from '../components/SectorDrawer'
import { projectsApi } from '../api/projects'
import type { Project, ParsedBP } from '../api/projects'
import { pollJob } from '../api/jobs'
import Badge from '../components/Badge'
import Spinner from '../components/Spinner'
import Modal from '../components/Modal'

const actionBtn: React.CSSProperties = { padding:'4px 10px', borderRadius:'var(--radius-sm)', border:'1px solid var(--border)', background:'transparent', color:'var(--text-secondary)', fontSize:11, cursor:'pointer', marginRight:4 }
const gradBtn: React.CSSProperties = { background:'linear-gradient(135deg,var(--accent),var(--accent-light))', color:'#fff', border:'none', borderRadius:'var(--radius-md)', padding:'7px 14px', fontSize:12, fontWeight:500 }

export default function Projects({ onGoToMatch }: { onGoToMatch: (id: number) => void }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [expanded, setExpanded] = useState<{id: number; type: 'report'|'research'} | null>(null)
  const [running, setRunning]   = useState<Record<number, boolean>>({})
  const [openSector, setOpenSector] = useState<string | null>(null)

  const reload = useCallback(() => projectsApi.list().then(setProjects).finally(() => setLoading(false)), [])
  useEffect(() => { reload() }, [reload])

  const filtered = projects.filter(p => !search || p.name.includes(search) || (p.sector||'').includes(search))

  function openPanel(p: Project, type: 'report'|'research') {
    setExpanded({ id: p.id, type })
    const hasCache = type === 'report' ? p.report_generated_at : p.research_generated_at
    if (hasCache) return
    setRunning(r => ({ ...r, [p.id]: true }))
    const start = type === 'report' ? projectsApi.startReport : projectsApi.startResearch
    start(p.id).then(({ job_id }) =>
      pollJob(job_id,
        () => { setRunning(r => ({ ...r, [p.id]: false })); reload() },
        () => setRunning(r => ({ ...r, [p.id]: false }))
      )
    )
  }

  return (
    <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
      <div style={{ flex: 1, minWidth: 0, overflowX: 'auto' }}>
      <div style={{ display:'flex', gap:10, marginBottom:16, alignItems:'center' }}>
        <h1 style={{ fontSize:18, fontWeight:600 }}>项目管理</h1>
        <button style={gradBtn} onClick={() => setShowUpload(true)}>＋ 上传 BP</button>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索名称、赛道…"
          style={{ background:'var(--bg-elevated)', border:'1px solid var(--border)', borderRadius:'var(--radius-md)', padding:'7px 12px', color:'var(--text-primary)', fontSize:12, width:220 }} />
        <span style={{ marginLeft:'auto', color:'var(--text-muted)', fontSize:12 }}>共 {filtered.length} 个</span>
      </div>

      {loading ? <Spinner /> : (
        <table style={{ width:'100%', borderCollapse:'collapse' }}>
          <thead><tr>
            {['项目名称','赛道','细分','阶段','所在地','操作'].map(h =>
              <th key={h} style={{ textAlign:'left', padding:'8px 12px', color:'var(--text-muted)', fontSize:11, fontWeight:500, textTransform:'uppercase', letterSpacing:.5, borderBottom:'1px solid var(--bg-elevated)' }}>{h}</th>
            )}
          </tr></thead>
          <tbody>
            {filtered.flatMap(p => {
              const isExp = expanded?.id === p.id
              const rows: React.ReactNode[] = [(
                <tr key={p.id} style={{ borderBottom:'1px solid var(--bg-elevated)' }}>
                  <td style={{ padding:'11px 12px', color:'#fff', fontWeight:500 }}>{p.name}</td>
                  <td style={{ padding:'11px 12px' }}>{p.sector && (
                    <ClickableSectorBadge name={p.sector} onClick={setOpenSector} />
                  )}</td>
                  <td style={{ padding:'11px 12px' }}>
                    {p.sub_sector ? (
                      <div style={{ display:'flex', flexWrap:'wrap', gap:3 }}>
                        {p.sub_sector.split(',').filter(Boolean).map(s => (
                          <ClickableSectorBadge key={s.trim()} name={s.trim()} onClick={setOpenSector} />
                        ))}
                      </div>
                    ) : <span style={{ color:'var(--text-secondary)' }}>—</span>}
                  </td>
                  <td style={{ padding:'11px 12px' }}>{p.stage && <Badge variant="amber">{p.stage}</Badge>}</td>
                  <td style={{ padding:'11px 12px', color:'var(--text-secondary)' }}>{p.location||'—'}</td>
                  <td style={{ padding:'11px 12px' }}>
                    <button style={actionBtn} onClick={() => openPanel(p,'report')}>📊 报告</button>
                    <button style={actionBtn} onClick={() => openPanel(p,'research')}>🔬 行研</button>
                    <button style={actionBtn} onClick={() => onGoToMatch(p.id)}>🔗 匹配</button>
                  </td>
                </tr>
              )]
              if (isExp && expanded) rows.push(
                <tr key={`${p.id}-panel`}>
                  <td colSpan={6} style={{ background:'var(--bg-surface)', padding:'16px 12px', borderBottom:'1px solid var(--bg-elevated)' }}>
                    <div style={{ display:'flex', alignItems:'center', marginBottom:10 }}>
                      <span style={{ fontWeight:600, flex:1 }}>
                        {expanded.type === 'report' ? `📊 ${p.name} — 项目报告` : `🔬 ${p.name} — 行研报告`}
                      </span>
                      <button onClick={() => setExpanded(null)} style={{ background:'none', border:'none', color:'var(--text-secondary)', cursor:'pointer' }}>✕ 关闭</button>
                    </div>
                    {running[p.id] ? (
                      <div style={{ display:'flex', alignItems:'center', gap:8, color:'var(--text-secondary)' }}><Spinner /> 生成中，请稍候…</div>
                    ) : expanded.type === 'report' ? (
                      <ReportPanel project={p} />
                    ) : (
                      <ResearchPanel project={p} />
                    )}
                  </td>
                </tr>
              )
              return rows
            })}
          </tbody>
        </table>
      )}

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSaved={() => { setShowUpload(false); reload() }} />}
      </div>
      {openSector && (
        <SectorDrawer
          key={openSector}
          sectorName={openSector}
          onClose={() => setOpenSector(null)}
          onJumpTo={(n) => setOpenSector(n)}
        />
      )}
    </div>
  )
}

function ReportPanel({ project }: { project: Project }) {
  const r = project.report_json ? JSON.parse(project.report_json) : {}
  const rows: [string, unknown][] = [['成立时间',r.founded_year],['总部',r.headquarters],['领域赛道',r.sector],['主要产品',r.main_products],['核心团队',r.team],['主要客户',r.customers]]
  return <div>{rows.map(([l,v]) => <div key={l} style={{ display:'flex', padding:'7px 0', borderBottom:'1px solid var(--bg-elevated)' }}><span style={{ width:90, color:'var(--text-muted)', fontSize:12 }}>{l}</span><span style={{ color:'var(--text-secondary)', fontSize:12 }}>{v as React.ReactNode||'—'}</span></div>)}</div>
}

function ResearchPanel({ project }: { project: Project }) {
  const r = project.research_json ? JSON.parse(project.research_json) : {}
  const sections: [string, unknown][] = [['行业概述',r.industry_overview],['市场规模 & 趋势',r.market_size],['本项目定位',r.target_positioning]]
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
      {sections.map(([l,v]) => (
        <div key={l}>
          <div style={{ color:'var(--text-muted)', fontSize:11, textTransform:'uppercase', marginBottom:4 }}>{l}</div>
          <div style={{ color:'var(--text-secondary)', fontSize:12, background:'var(--bg-elevated)', borderRadius:6, padding:'8px 12px' }}>{v as React.ReactNode||'—'}</div>
        </div>
      ))}
    </div>
  )
}

function UploadModal({ onClose, onSaved }: { onClose:()=>void; onSaved:()=>void }) {
  const [parsed, setParsed] = useState<ParsedBP|null>(null)
  const [parsing, setParsing] = useState(false)
  const [form, setForm] = useState({ name:'', sector:'', sub_sector:'', stage:'', location:'', description:'', highlights:'', financing_need:'' })

  async function pick(file: File) {
    setParsing(true)
    try {
      const d = await projectsApi.parse(file)
      setParsed(d)
      setForm({ name:d.name||d.default_name||'', sector:d.sector||'', sub_sector:d.sub_sector||'', stage:d.stage||'', location:d.location||'', description:d.description||'', highlights:d.highlights||'', financing_need:d.financing_need||'' })
    } finally { setParsing(false) }
  }

  const inp = (style?: React.CSSProperties): React.CSSProperties => ({ background:'var(--bg-elevated)', border:'1px solid var(--border)', borderRadius:6, padding:'7px 10px', color:'var(--text-primary)', fontSize:13, ...style })

  return (
    <Modal title="上传 BP" onClose={onClose}>
      {!parsed && !parsing && (
        <label style={{ display:'block', border:'2px dashed var(--border)', borderRadius:8, padding:32, textAlign:'center', cursor:'pointer', color:'var(--text-secondary)' }}>
          点击选择 PDF 或 PPTX 文件
          <input type="file" accept=".pdf,.pptx,.ppt" style={{ display:'none' }} onChange={e => e.target.files?.[0] && pick(e.target.files[0])} />
        </label>
      )}
      {parsing && <div style={{ textAlign:'center', padding:32 }}><Spinner size={24} /><p style={{ marginTop:12, color:'var(--text-secondary)' }}>Claude 正在解析…</p></div>}
      {parsed && !parsing && (
        <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
          {([['项目名称','name'],['赛道','sector'],['细分','sub_sector'],['融资阶段','stage'],['所在地','location'],['融资需求','financing_need']] as [string,keyof typeof form][]).map(([l,k]) => (
            <div key={k} style={{ display:'flex', flexDirection:'column', gap:4 }}>
              <label style={{ color:'var(--text-secondary)', fontSize:12 }}>{l}</label>
              <input value={form[k]} onChange={e => setForm(f=>({...f,[k]:e.target.value}))} style={inp()} />
            </div>
          ))}
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            <label style={{ color:'var(--text-secondary)', fontSize:12 }}>项目简介</label>
            <textarea value={form.description} rows={3} onChange={e => setForm(f=>({...f,description:e.target.value}))} style={inp({resize:'vertical'})} />
          </div>
          <button onClick={async () => { await projectsApi.create({...form, file_path:parsed.file_path}); onSaved() }} style={{ ...gradBtn, marginTop:8, padding:'9px 16px', fontSize:13, fontWeight:500 }}>✅ 确认保存</button>
        </div>
      )}
    </Modal>
  )
}
