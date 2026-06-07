'use client'

export default function Home() {
  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      margin: 0,
      padding: 0,
      overflow: 'hidden',
      position: 'relative',
    }}>
      <iframe
        src="/admin?XTransformPort=8080"
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          margin: 0,
          padding: 0,
          display: 'block',
        }}
        title="Elyanivery Admin Dashboard"
      />
    </div>
  )
}
