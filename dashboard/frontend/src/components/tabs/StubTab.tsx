interface Props {
  title: string
  description: string
}

export default function StubTab({ title, description }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 300, textAlign: 'center' }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%', background: 'var(--color-surface)',
        border: '2px dashed var(--color-border)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: 24, marginBottom: 20,
      }}>🚧</div>
      <h2 style={{ margin: '0 0 10px', fontSize: 18, fontWeight: 700 }}>{title}</h2>
      <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: 14, maxWidth: 480, lineHeight: 1.6 }}>
        {description}
      </p>
      <div className="badge badge-pending" style={{ marginTop: 20, fontSize: 12 }}>Coming in v2</div>
    </div>
  )
}
