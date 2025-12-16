import React from 'react'

interface ImagePreviewProps {
  src: string
  alt?: string
  name?: string
  onClose: () => void
}

const ImagePreview: React.FC<ImagePreviewProps> = ({ src, alt, name, onClose }) => {
  const [zoom, setZoom] = React.useState(1)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === '+') setZoom((z) => Math.min(3, z + 0.25))
      if (e.key === '-') setZoom((z) => Math.max(0.25, z - 0.25))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey) {
      e.preventDefault()
      const delta = e.deltaY > 0 ? -0.1 : 0.1
      setZoom((z) => Math.max(0.25, Math.min(3, +(z + delta).toFixed(2))))
    }
  }

  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = src
    a.download = name || ''
    a.target = '_blank'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }

  return (
    <div style={{ position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1200 }}>
      <div
        onClick={onClose}
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)' }}
      />

      <div style={{ position: 'relative', maxWidth: '95vw', maxHeight: '95vh', zIndex: 1201, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', justifyContent: 'flex-end', marginBottom: '8px' }}>
          <button onClick={() => setZoom(1)} className="btn-secondary">Fit</button>
          <button onClick={() => setZoom((z) => Math.max(0.25, +(z - 0.25).toFixed(2)))} className="btn-secondary">-</button>
          <button onClick={() => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))} className="btn-secondary">+</button>
          <button onClick={handleDownload} className="btn-primary">Download</button>
          <button onClick={onClose} className="btn-secondary">Close</button>
        </div>

        <div onWheel={handleWheel} style={{ background: 'var(--bg-panel)', borderRadius: 8, padding: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', maxWidth: '95vw', maxHeight: '95vh', overflow: 'auto' }}>
          {loading && !error && (
            <div style={{ position: 'absolute', color: 'var(--text-secondary)' }}>Loading image...</div>
          )}

          {error ? (
            <div style={{ color: 'var(--negative-color)' }}>{error}</div>
          ) : (
            <img
              src={src}
              alt={alt || name || 'preview'}
              onLoad={() => setLoading(false)}
              onError={() => { setLoading(false); setError('Failed to load image') }}
              style={{ transform: `scale(${zoom})`, transition: 'transform 0.1s ease', maxWidth: '100%', maxHeight: '80vh', objectFit: 'contain', borderRadius: 6 }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default ImagePreview
