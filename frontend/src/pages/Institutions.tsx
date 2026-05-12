import { useState, useEffect, useCallback } from 'react'
import { institutionsApi, Institution } from '../api/institutions'
import { pollJob } from '../api/jobs'
import Badge from '../components/Badge'
import Spinner from '../components/Spinner'

type Tab = 'list'|'add'|'import'

export default function Institutions() {
  const [tab, setTab] = useState<Tab>('list')
  const [institutions, setInstitutions] = useState<Institution[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [scraping, setScraping] = useState<Record<number,boolean>>({})

  const reload = useCallback(() => institutionsApi.list().then(setInstitutions).finally(()=>setLoading(false)),[])
  useEffect(()=>{ reload() },[reload])

  const filtered = institutions.filter(i => !search || i.name.includes(search))

  function rescrape(inst: Institution) {
    setScraping(s=>({...s,[inst.id]:true}))
    institutionsApi.scrape(inst.id).then(({job_id}) =>
      pollJob(job_id, ()=>{setScraping(s=>({...s,[inst.id]:false}));reload()}, ()=>setScraping(s=>({...s,[inst.id]:false})))
    )
  }

  const tabBtn = (t: Tab, l: string) => (
    <button key={t} onClick={()=>setTab(t)} style={{ padding:'8px 16px', background:'none', border:'none', cursor:'pointer', color:tab===t?'var(--text-primary)':'var(--text-secondary)', borderBottom:`2px solid ${tab===t?'var(--accent)':'transparent'}`, marginBottom:-1, fontSize:13 }}>{l}</button>
  )

  return (
    <div>
      <h1 style={{ fontSize:18, fontWeight:600, marginBottom:20 }}>机构管理</h1>
      <div style={{ display:'flex', borderBottom:'1px solid var(--border)', marginBottom:20 }}>
        {tabBtn('list','机构列表')}{tabBtn('add','新增机构')}{tabBtn('import','导入 Excel')}
      </div>

      {tab==='list' && <>
        <div style={{ display:'flex', gap:10, marginBottom:16, alignItems:'center' }}>
          <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索机构名称…" style={{ background:'var(--bg-elevated)', border:'1px solid var(--border)', borderRadius:6, padding:'7px 12px', color:'var(--text-primary)', fontSize:12, width:220 }} />
          <span style={{ marginLeft:'auto', color:'var(--text-muted)', fontSize:12 }}>共 {filtered.length} 家</span>
        </div>
        {loading ? <Spinner /> : (
          <table style={{ width:'100%', borderCollapse:'collapse' }}>
            <thead><tr>
              {['机构名称','关注赛道','偏好阶段','操作'].map(h=><th key={h} style={{ textAlign:'left', padding:'8px 12px', color:'var(--text-muted)', fontSize:11, fontWeight:500, textTransform:'uppercase', letterSpacing:.5, borderBottom:'1px solid var(--bg-elevated)' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {filtered.map(inst=>(
                <tr key={inst.id} style={{ borderBottom:'1px solid var(--bg-elevated)' }}>
                  <td style={{ padding:'11px 12px', color:'#fff', fontWeight:500 }}>{inst.name}</td>
                  <td style={{ padding:'11px 12px' }}>{(inst.preferred_sectors||'').split(',').filter(Boolean).slice(0,3).map(s=><Badge key={s} variant="blue">{s.trim()}</Badge>)}</td>
                  <td style={{ padding:'11px 12px' }}>{inst.preferred_stages && <Badge variant="amber">{inst.preferred_stages.split(',')[0]}</Badge>}</td>
                  <td style={{ padding:'11px 12px' }}>
                    {scraping[inst.id] ? <Spinner size={14}/> : <button onClick={()=>rescrape(inst)} style={{ padding:'4px 10px', borderRadius:4, border:'1px solid var(--border)', background:'transparent', color:'var(--text-secondary)', fontSize:11, cursor:'pointer' }}>🔄 刷新</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </>}

      {tab==='add' && <AddForm onSaved={()=>{setTab('list');reload()}} />}
      {tab==='import' && <ImportForm onSaved={()=>{setTab('list');reload()}} />}
    </div>
  )
}

function AddForm({ onSaved }: { onSaved:()=>void }) {
  const [form, setForm] = useState({ name:'', location:'', known_preferences:'', contact_name:'', contact_wechat:'', fa_fee_note:'', response_style:'' })
  const [saving, setSaving] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault(); if (!form.name.trim()) return
    setSaving(true); try { await institutionsApi.create(form); onSaved() } finally { setSaving(false) }
  }

  const inp: React.CSSProperties = { background:'var(--bg-elevated)', border:'1px solid var(--border)', borderRadius:6, padding:'7px 10px', color:'var(--text-primary)', fontSize:13 }
  const fields: [string, keyof typeof form, boolean][] = [['机构名称 *','name',false],['总部地点','location',false],['联系人','contact_name',false],['联系方式','contact_wechat',false],['FA 费用','fa_fee_note',false],['已知偏好','known_preferences',true]]

  return (
    <form onSubmit={submit} style={{ maxWidth:480, display:'flex', flexDirection:'column', gap:12 }}>
      {fields.map(([l,k,ta])=>(
        <div key={k} style={{ display:'flex', flexDirection:'column', gap:4 }}>
          <label style={{ color:'var(--text-secondary)', fontSize:12 }}>{l}</label>
          {ta ? <textarea value={form[k]} rows={3} onChange={e=>setForm(f=>({...f,[k]:e.target.value}))} style={{...inp,resize:'vertical'}} />
               : <input value={form[k]} onChange={e=>setForm(f=>({...f,[k]:e.target.value}))} style={inp} />}
        </div>
      ))}
      <button type="submit" disabled={saving} style={{ background:'linear-gradient(135deg,var(--accent),var(--accent-light))', color:'#fff', border:'none', borderRadius:6, padding:'9px 16px', fontWeight:500, fontSize:13, marginTop:8 }}>
        {saving?'保存中…':'➕ 新增并自动补全'}
      </button>
    </form>
  )
}

function ImportForm({ onSaved }: { onSaved:()=>void }) {
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<{created:number}|null>(null)
  async function pick(file: File) {
    setImporting(true); try { const r = await institutionsApi.importExcel(file); setResult(r); setTimeout(onSaved,1500) } finally { setImporting(false) }
  }
  return importing ? <div style={{ display:'flex', alignItems:'center', gap:8, color:'var(--text-secondary)' }}><Spinner/> 导入中…</div>
    : result ? <p style={{ color:'var(--success)' }}>✅ 成功导入 {result.created} 家机构</p>
    : <label style={{ display:'block', border:'2px dashed var(--border)', borderRadius:8, padding:32, textAlign:'center', cursor:'pointer', color:'var(--text-secondary)' }}>点击选择 Excel 文件<input type="file" accept=".xlsx" style={{ display:'none' }} onChange={e=>e.target.files?.[0]&&pick(e.target.files[0])}/></label>
}
