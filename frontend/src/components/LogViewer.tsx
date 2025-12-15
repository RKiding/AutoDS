import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import remarkGfm from 'remark-gfm'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { LogEntry } from '../types'

interface LogViewerProps {
  logs: LogEntry[]
  onClear: () => void
}

const LogViewer: React.FC<LogViewerProps> = ({ logs, onClear }) => {
  const logsEndRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    return date.toLocaleTimeString()
  }

  return (
    <div className="log-viewer panel">
      <div className="panel-header">
        <h2><i className="fas fa-terminal"></i> Execution Logs</h2>
        <div className="panel-actions">
          <button onClick={onClear}>
            <i className="fas fa-trash"></i> Clear
          </button>
        </div>
      </div>
      <div className="panel-content">
        {logs.length === 0 ? (
          <div className="empty-state">
            <i className="fas fa-comment-slash"></i>
            <p>No logs yet. Start an agent to see execution logs.</p>
          </div>
        ) : (
          <>
            {logs.map((log, idx) => (
              <div key={idx} className={`log-entry log-${log.type}`}>
                <span className="log-timestamp">{formatTimestamp(log.timestamp)}</span>
                <div className="log-message markdown-content">
                  <ReactMarkdown
                    remarkPlugins={[remarkMath, remarkGfm]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {log.message}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
            <div ref={logsEndRef} />
          </>
        )}
      </div>
    </div>
  )
}

export default LogViewer
