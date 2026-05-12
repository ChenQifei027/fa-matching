import { useState, useEffect } from 'react'
import { settingsApi, Settings } from '../api/settings'
import Spinner from '../components/Spinner'

const inp: React.CSSProperties = { flex:1, background:'var(--bg-elevated)', border:'1px solid var(--border)', borderRadius:6, padding:'6px 10px', color:'var(--text-primary)', fontSize:12 }
const ghostBtn: React.CSSProperties = { background:'transparent', color:'var(--text-secondary)', border:'1px solid var(--border)', borderRadius:6, padding:'7px 14px', fontSize:12, cursor:'pointer' }

export default function Settings() {
  const [settings, setSettings] = useState<Settings|null>(null)
  const [form, setForm] = useState({ anthropic_api_key:'', model:'' })
  const [verifying, setVerifying] = useState(false)
  const [verified, setVerified] = useState<boolean|null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<number|null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(()=>{ settingsApi.get().then(s=>{ setSettings(s); setForm({ anthropic_api_key:s.anthropic_api_key, model:s.model }) }) },[])

  async function verify() { setVerifying(true); setVerified(null); try { const {configured} = await settingsApi.verifyLlm(); setVerified(configured) } finally { setVerifying(false) } }
  async function sync()   { setSyncing(true); setSyncResult(null); try { const {synced} = await settingsApi.syncCookies(); setSyncResult(synced) } finally { setSyncing(false) } }
  async function save()   { setSaving(true); try { await settingsApi.update(form) } finally { setSaving(false) } }

  if (!settings) return <Spinner />

  return (
    <div style={{ maxWidth:560 }}>
      <h1 style={{ fontSize:18, fontWeight:600, marginBottom:24 }}>设置</h1>

      <section style={{ background:'var(--bg-surface)', border:'1px solid var(--border)', borderRadius:8, padding:20, marginBottom:16 }}>
        <h2 style={{ fontSize:14, fontWeight:600, marginBottom:14 }}>推理模型配置</h2>
        {[['Anthropic API Key','anthropic_api_key','password'],['模型','model','text']].map(([l,k,t])=>(
          <div key={k} style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
            <span style={{ color:'var(--text-secondary)', fontSize:12, width:130, flexShrink:0 }}>{l}</span>
            <input type={t} value={form[k as keyof typeof form]} onChange={e=>setForm(f=>({...f,[k]:e.target.value}))} style={inp} />
          </div>
        ))}
        <div style={{ display:'flex', gap:8, marginTop:4, alignItems:'center' }}>
          <button onClick={save} disabled={saving} style={ghostBtn}>{saving?'保存中…':'💾 保存'}</button>
          <button onClick={verify} disabled={verifying} style={ghostBtn}>{verifying?<Spinner size={12}/>:'验证'}</button>
          {verified===true  && <span style={{ color:'var(--success)', fontSize:12 }}>✅ 已连接</span>}
          {verified===false && <span style={{ color:'var(--danger)', fontSize:12 }}>❌ 连接失败</span>}
        </div>
      </section>

      <section style={{ background:'var(--bg-surface)', border:'1px solid var(--border)', borderRadius:8, padding:20 }}>
        <h2 style={{ fontSize:14, fontWeight:600, marginBottom:14 }}>IT 桔子 · 数据抓取</h2>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
          <span style={{ color:'var(--text-secondary)', fontSize:12, width:130, flexShrink:0 }}>Chrome Cookie</span>
          <span style={{ width:8, height:8, borderRadius:'50%', background:'var(--success)', display:'inline-block', marginRight:6 }}/>
          <span style={{ color:'var(--success)', fontSize:12 }}>已检测到 itjuzi.com 登录态</span>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ width:130, flexShrink:0 }}/>
          <button onClick={sync} disabled={syncing} style={ghostBtn}>{syncing?<Spinner size={12}/>:'手动同步'}</button>
          {syncResult!==null && <span style={{ color:'var(--success)', fontSize:12 }}>同步了 {syncResult} 条 Cookie</span>}
        </div>
      </section>
    </div>
  )
}
