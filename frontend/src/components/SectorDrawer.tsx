import { useState, useEffect, useRef } from 'react'
import { sectorsApi } from '../api/sectors'
import type { SectorExplanation } from '../api/sectors'
import { pollJob } from '../api/jobs'

interface DrawerProps {
  sectorName: string
  onClose: () => void
  onJumpTo: (name: string) => void
}

type State =
  | { kind: 'loading' }
  | { kind: 'data', data: SectorExplanation }
  | { kind: 'error', message: string }

export default function SectorDrawer({ sectorName, onClose, onJumpTo }: DrawerProps) {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [regenerating, setRegenerating] = useState(false)
  const cancelPoll = useRef<(() => void) | null>(null)

  useEffect(() => {
    let cancelled = false
    cancelPoll.current?.()

    sectorsApi.get(sectorName).then(hit => {
      if (cancelled) return
      if (hit) {
        setState({ kind: 'data', data: hit })
      } else {
        sectorsApi.generate(sectorName).then(({ job_id }) => {
          if (cancelled) return
          cancelPoll.current = pollJob(
            job_id,
            async () => {
              const fresh = await sectorsApi.get(sectorName)
              if (cancelled) return
              if (fresh) setState({ kind: 'data', data: fresh })
              else setState({ kind: 'error', message: '生成完成但未读到结果' })
            },
            (j) => !cancelled && setState({ kind: 'error', message: j.error || '生成失败' })
          )
        }).catch(e => !cancelled && setState({ kind: 'error', message: String(e) }))
      }
    }).catch(e => !cancelled && setState({ kind: 'error', message: String(e) }))

    return () => { cancelled = true; cancelPoll.current?.() }
  }, [sectorName])

  async function regenerate() {
    cancelPoll.current?.()
    setRegenerating(true)
    setState({ kind: 'loading' })
    try {
      const { job_id } = await sectorsApi.generate(sectorName, true)
      cancelPoll.current = pollJob(
        job_id,
        async () => {
          const fresh = await sectorsApi.get(sectorName)
          if (fresh) setState({ kind: 'data', data: fresh })
          setRegenerating(false)
        },
        (j) => { setState({ kind: 'error', message: j.error || '重新生成失败' }); setRegenerating(false) }
      )
    } catch (e) {
      setState({ kind: 'error', message: String(e) })
      setRegenerating(false)
    }
  }

  return (
    <aside style={{
      width: 520, flexShrink: 0, alignSelf: 'flex-start',
      position: 'sticky', top: 0,
      border: '1px solid var(--border)', borderRadius: 8,
      background: 'var(--bg-surface)', overflow: 'hidden'
    }}>
      <div style={{
        padding: '14px 16px 14px 20px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10
      }}>
        <span style={{
          fontWeight: 600, fontSize: 15, color: '#fff', flex: 1,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
        }}>{sectorName}</span>
        <button onClick={onClose} aria-label="关闭" title="关闭" style={{
          background: 'transparent', border: 'none', color: 'var(--text-muted)',
          fontSize: 20, padding: '0 4px', lineHeight: 1, cursor: 'pointer'
        }}>×</button>
      </div>

      <div style={{
        padding: '8px 20px', borderBottom: '1px solid var(--border)',
        background: 'rgba(245,158,11,0.06)',
        display: 'flex', alignItems: 'center', gap: 12,
        fontSize: 11, color: 'var(--text-secondary)'
      }}>
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--warning)' }} />
        <span>AI 生成,仅供参考</span>
        {state.kind === 'data' && state.data.generated_at && (
          <>
            <span>·</span>
            <span>上次生成 {state.data.generated_at.slice(0, 10)}</span>
          </>
        )}
        <button onClick={regenerate} disabled={regenerating || state.kind === 'loading'} style={{
          marginLeft: 'auto',
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--text-secondary)', fontSize: 11,
          padding: '3px 10px', borderRadius: 4, cursor: 'pointer'
        }}>↻ 重新生成</button>
      </div>

      <div style={{ padding: 20, maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
        {state.kind === 'loading' && <SkeletonView />}

        {state.kind === 'error' && (
          <div style={{ color: 'var(--danger)', fontSize: 13 }}>
            {state.message}
            <div style={{ marginTop: 8 }}>
              <button onClick={regenerate} style={{
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text-secondary)', padding: '4px 12px',
                borderRadius: 4, fontSize: 12, cursor: 'pointer'
              }}>重试</button>
            </div>
          </div>
        )}

        {state.kind === 'data' && <DataView data={state.data} onJumpTo={onJumpTo} />}
      </div>
    </aside>
  )
}

const SKEL_BASE: React.CSSProperties = {
  background: 'linear-gradient(90deg, var(--bg-elevated) 0%, rgba(91,91,214,0.12) 50%, var(--bg-elevated) 100%)',
  backgroundSize: '200% 100%',
  animation: 'shimmer 1.4s linear infinite',
  borderRadius: 4,
}

function SkelLine({ w = '100%', h = 14 }: { w?: string; h?: number }) {
  return <div style={{ ...SKEL_BASE, width: w, height: h, marginBottom: 8 }} />
}

function SkeletonView() {
  const h3: React.CSSProperties = {
    fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '.5px', fontWeight: 500, marginBottom: 8
  }
  return (
    <>
      <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 16 }}>
        AI 生成中…首次生成可能需要十几秒
      </p>
      <div style={{ marginBottom: 20 }}>
        <div style={h3}>是什么</div>
        <SkelLine /><SkelLine /><SkelLine w="60%" />
      </div>
      <div style={{ marginBottom: 20 }}>
        <div style={h3}>行业发展</div>
        <SkelLine /><SkelLine w="80%" /><SkelLine />
      </div>
      <div>
        <div style={h3}>头部公司</div>
        <div style={{ ...SKEL_BASE, height: 40, marginBottom: 8 }} />
        <div style={{ ...SKEL_BASE, height: 40 }} />
      </div>
    </>
  )
}

function DataView({ data, onJumpTo }: { data: SectorExplanation; onJumpTo: (name: string) => void }) {
  const h3: React.CSSProperties = {
    fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '.5px', fontWeight: 500, marginBottom: 8
  }
  const section: React.CSSProperties = { marginBottom: 20 }
  return (
    <>
      <div style={section}>
        <div style={h3}>是什么</div>
        <p style={{ fontSize: 13, lineHeight: 1.65 }}>{data.description || '—'}</p>
      </div>
      <div style={section}>
        <div style={h3}>行业发展</div>
        <p style={{ fontSize: 13, lineHeight: 1.65 }}>{data.industry_overview || '—'}</p>
      </div>
      <div style={section}>
        <div style={h3}>头部公司</div>
        {data.top_companies.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.top_companies.map(c => (
              <div key={c.name} style={{
                padding: '8px 10px', borderRadius: 6,
                background: 'var(--bg-elevated)', border: '1px solid var(--bg-elevated)'
              }}>
                <div style={{ color: '#fff', fontWeight: 500, fontSize: 13 }}>{c.name}</div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{c.desc}</div>
              </div>
            ))}
          </div>
        )}
      </div>
      {data.synonyms.length > 0 && (
        <div style={section}>
          <div style={h3}>同义词候选(LLM 给出,可点跳转)</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {data.synonyms.map(s => (
              <span key={s}
                role="button"
                tabIndex={0}
                onClick={() => onJumpTo(s)}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onJumpTo(s) } }}
                style={{
                  fontSize: 12, padding: '3px 10px', borderRadius: 4,
                  background: 'rgba(139,92,246,0.12)', color: 'var(--accent-light)',
                  border: '1px solid rgba(139,92,246,0.3)', cursor: 'pointer'
                }}>{s}</span>
            ))}
          </div>
        </div>
      )}
    </>
  )
}

interface BadgeProps {
  name: string
  onClick: (name: string) => void
}

export function ClickableSectorBadge({ name, onClick }: BadgeProps) {
  return (
    <span
      role="button"
      tabIndex={0}
      onClick={() => onClick(name)}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(name) } }}
      style={{
      fontSize: 11, padding: '2px 8px', borderRadius: 3,
      background: 'rgba(91,91,214,0.18)', color: '#a8a4ff',
      border: '1px dashed transparent',
      cursor: 'pointer', userSelect: 'none', lineHeight: 1.6,
      display: 'inline-block',
      transition: 'all .12s ease',
    }}
    onMouseEnter={e => {
      e.currentTarget.style.background = 'rgba(91,91,214,0.32)'
      e.currentTarget.style.borderColor = 'rgba(139,92,246,0.6)'
      e.currentTarget.style.color = '#fff'
    }}
    onMouseLeave={e => {
      e.currentTarget.style.background = 'rgba(91,91,214,0.18)'
      e.currentTarget.style.borderColor = 'transparent'
      e.currentTarget.style.color = '#a8a4ff'
    }}
    >{name}</span>
  )
}
