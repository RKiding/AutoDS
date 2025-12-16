import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import API_URL from '../config/api'
import ImagePreview from './ImagePreview'

interface MarkdownViewerProps {
  filePath: string
  onClose: () => void
}

const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ filePath, onClose }) => {
  const [content, setContent] = React.useState<string>('')
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [imagePreviewSrc, setImagePreviewSrc] = React.useState<string | null>(null)
  const [imagePreviewAlt, setImagePreviewAlt] = React.useState<string | undefined>(undefined)

  React.useEffect(() => {
    loadMarkdown()
  }, [filePath])

  const loadMarkdown = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_URL}/api/file-preview?path=${encodeURIComponent(filePath)}`)
      const data = await response.json()
      if (data.content) {
        setContent(data.content)
      } else {
        setError(data.message || 'Failed to load file')
      }
    } catch (err) {
      setError(`Error loading file: ${err}`)
    } finally {
      setLoading(false)
    }
  }

  const openImagePreview = (src?: string, alt?: string) => {
    if (!src) return
    // If absolute URL or data URI, use directly
    if (src.startsWith('http') || src.startsWith('data:') || src.startsWith('/')) {
      setImagePreviewSrc(src)
      setImagePreviewAlt(alt)
      return
    }
    // Otherwise assume it's a workspace-relative path and use download endpoint
    const url = `${API_URL}/api/download-file?path=${encodeURIComponent(src)}`
    setImagePreviewSrc(url)
    setImagePreviewAlt(alt)
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        background: 'var(--bg-panel)',
        borderRadius: '12px',
        boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)',
        display: 'flex',
        flexDirection: 'column',
        width: '90%',
        maxWidth: '900px',
        height: '90vh',
        maxHeight: '800px'
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 24px',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0 }}>
            <i className="fas fa-file-alt" style={{ fontSize: '18px', color: 'var(--accent-color)' }}></i>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{
                fontSize: '14px',
                fontWeight: 600,
                color: 'var(--text-primary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }} title={filePath}>
                {filePath.split('/').pop()}
              </div>
              <div style={{
                fontSize: '11px',
                color: 'var(--text-secondary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }} title={filePath}>
                {filePath}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '20px',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
              padding: '4px 8px',
              borderRadius: '4px',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-hover)'
              e.currentTarget.style.color = 'var(--text-primary)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'none'
              e.currentTarget.style.color = 'var(--text-secondary)'
            }}
          >
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* Content Area */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '24px',
          minHeight: 0
        }}>
          {loading ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-secondary)'
            }}>
              <div style={{ textAlign: 'center' }}>
                <i className="fas fa-spinner fa-spin" style={{ fontSize: '24px', marginBottom: '12px', display: 'block' }}></i>
                <span>Loading markdown...</span>
              </div>
            </div>
          ) : error ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--negative-color)',
              textAlign: 'center'
            }}>
              <div>
                <i className="fas fa-exclamation-circle" style={{ fontSize: '24px', marginBottom: '12px', display: 'block' }}></i>
                <span>{error}</span>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-primary)' }} className="markdown-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  h1: ({ ...props }) => (
                    <h1 style={{
                      fontSize: '28px',
                      fontWeight: 700,
                      marginTop: '24px',
                      marginBottom: '16px',
                      paddingBottom: '12px',
                      borderBottom: '1px solid var(--border-color)',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  h2: ({ ...props }) => (
                    <h2 style={{
                      fontSize: '24px',
                      fontWeight: 600,
                      marginTop: '20px',
                      marginBottom: '12px',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  h3: ({ ...props }) => (
                    <h3 style={{
                      fontSize: '20px',
                      fontWeight: 600,
                      marginTop: '16px',
                      marginBottom: '10px',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  h4: ({ ...props }) => (
                    <h4 style={{
                      fontSize: '16px',
                      fontWeight: 600,
                      marginTop: '14px',
                      marginBottom: '8px',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  h5: ({ ...props }) => (
                    <h5 style={{
                      fontSize: '14px',
                      fontWeight: 600,
                      marginTop: '12px',
                      marginBottom: '6px',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  h6: ({ ...props }) => (
                    <h6 style={{
                      fontSize: '12px',
                      fontWeight: 600,
                      marginTop: '10px',
                      marginBottom: '4px',
                      color: 'var(--text-secondary)'
                    }} {...props} />
                  ),
                  p: ({ ...props }) => (
                    <p style={{
                      marginBottom: '12px',
                      lineHeight: '1.6',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  ul: ({ ...props }) => (
                    <ul style={{
                      marginLeft: '20px',
                      marginBottom: '12px',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  ol: ({ ...props }) => (
                    <ol style={{
                      marginLeft: '20px',
                      marginBottom: '12px',
                      color: 'var(--text-primary)'
                    }} {...props} />
                  ),
                  li: ({ ...props }) => (
                    <li style={{
                      marginBottom: '6px',
                      lineHeight: '1.6'
                    }} {...props} />
                  ),
                  blockquote: ({ ...props }) => (
                    <blockquote style={{
                      borderLeft: '4px solid var(--accent-color)',
                      paddingLeft: '12px',
                      marginLeft: 0,
                      marginBottom: '12px',
                      color: 'var(--text-secondary)',
                      fontStyle: 'italic'
                    }} {...props} />
                  ),
                  code: ({ inline, ...props }) => inline ? (
                    <code style={{
                      background: 'var(--bg-panel)',
                      padding: '2px 6px',
                      borderRadius: '3px',
                      fontFamily: 'monospace',
                      fontSize: '13px',
                      color: 'var(--accent-color)',
                      border: '1px solid var(--border-color)'
                    }} {...props} />
                  ) : (
                    <code style={{
                      background: 'var(--bg-panel)',
                      padding: '12px',
                      borderRadius: '6px',
                      display: 'block',
                      marginBottom: '12px',
                      fontFamily: 'monospace',
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      border: '1px solid var(--border-color)',
                      overflow: 'auto'
                    }} {...props} />
                  ),
                  pre: ({ ...props }) => (
                    <pre style={{
                      background: 'var(--bg-panel)',
                      padding: '12px',
                      borderRadius: '6px',
                      marginBottom: '12px',
                      border: '1px solid var(--border-color)',
                      overflow: 'auto'
                    }} {...props} />
                  ),
                  table: ({ ...props }) => (
                    <table style={{
                      borderCollapse: 'collapse',
                      width: '100%',
                      marginBottom: '12px',
                      border: '1px solid var(--border-color)'
                    }} {...props} />
                  ),
                  thead: ({ ...props }) => (
                    <thead style={{
                      background: 'var(--bg-panel)',
                      borderBottom: '2px solid var(--border-color)'
                    }} {...props} />
                  ),
                  th: ({ ...props }) => (
                    <th style={{
                      padding: '8px 12px',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      borderRight: '1px solid var(--border-color)'
                    }} {...props} />
                  ),
                  td: ({ ...props }) => (
                    <td style={{
                      padding: '8px 12px',
                      borderRight: '1px solid var(--border-color)',
                      borderBottom: '1px solid var(--border-color)'
                    }} {...props} />
                  ),
                  tr: ({ ...props }) => (
                    <tr style={{
                      borderBottom: '1px solid var(--border-color)'
                    }} {...props} />
                  ),
                  a: ({ ...props }) => (
                    <a style={{
                      color: 'var(--accent-color)',
                      textDecoration: 'underline',
                      cursor: 'pointer'
                    }} {...props} />
                  ),
                  img: ({ ...props }: any) => (
                    <img
                      onClick={() => openImagePreview(props.src, props.alt)}
                      style={{
                        maxWidth: '100%',
                        height: 'auto',
                        marginBottom: '12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-color)',
                        cursor: 'pointer'
                      }}
                      {...props}
                    />
                  ),
                  hr: ({ ...props }) => (
                    <hr style={{
                      border: 'none',
                      borderTop: '2px solid var(--border-color)',
                      margin: '20px 0'
                    }} {...props} />
                  )
                }}
              >
                {content}
              </ReactMarkdown>
              {imagePreviewSrc && (
                <ImagePreview src={imagePreviewSrc} alt={imagePreviewAlt} onClose={() => setImagePreviewSrc(null)} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default MarkdownViewer
