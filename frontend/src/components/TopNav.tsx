interface Props { current: string; onNavigate: (p: string) => void }
export default function TopNav({ current, onNavigate }: Props) {
  return <nav style={{ height: 44, background: '#0f0f1a', borderBottom: '1px solid #2a2a4a', display: 'flex', alignItems: 'center', padding: '0 20px' }}>
    {['projects','institutions','matching','settings'].map(p => (
      <button key={p} onClick={() => onNavigate(p)} style={{ margin: '0 4px', padding: '5px 12px', background: 'none', border: 'none', color: current === p ? '#e2e2e8' : '#888', cursor: 'pointer' }}>{p}</button>
    ))}
  </nav>
}
