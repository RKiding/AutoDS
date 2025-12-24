import React from 'react'
import API_URL from '../config/api'
import { SystemStatus, SystemConfig, LogEntry } from '../types'
import ChatInterface from './ChatInterface'
import FileManager from './FileManager'
import ProgressBar from './ProgressBar'
import '../styles/console.css'

const AgentConsole: React.FC = () => {
  const [status, setStatus] = React.useState<SystemStatus>({
    is_running: false,
    waiting_for_input: false,
    logs: [],
    active_workspace: null
  })
  const [config, setConfig] = React.useState<SystemConfig>({
    enable_search_tool: true,
    enable_hitl: true,
    enable_simple_task_check: true,
    enable_deep_research: true,
    deep_research_use_simple_goal: false
  })
  const [showFiles, setShowFiles] = React.useState(false)
  const [showHistory, setShowHistory] = React.useState(false)
  const [hasStarted, setHasStarted] = React.useState(false)
  const [stopRequested, setStopRequested] = React.useState(false)
  const [stopTimeout, setStopTimeout] = React.useState<NodeJS.Timeout | null>(null)

  // Theme state: 'dark' or 'light'
  const [theme, setTheme] = React.useState<'dark' | 'light'>(() => {
    // Check localStorage first
    const saved = localStorage.getItem('autods_theme')
    if (saved === 'light' || saved === 'dark') return saved
    // Check system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light'
    }
    return 'dark'
  })

  // Apply theme to document
  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('autods_theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark')
  }

  const [workspaceRoot, setWorkspaceRoot] = React.useState<string | null>(null)
  const [historyList, setHistoryList] = React.useState<Array<any>>([])
  // Sessions stored in localStorage as full chat/workspace sessions
  const [sessions, setSessions] = React.useState<Array<any>>([])
  const [currentSessionId, setCurrentSessionId] = React.useState<number | null>(null)
  // Track which session (if any) is currently running so we can stream live logs into it
  const [liveSessionId, setLiveSessionId] = React.useState<number | null>(null)

  const SESSIONS_KEY = 'autods_sessions'

  // Ref for debouncing log saves to backend
  const saveLogsTimeoutRef = React.useRef<NodeJS.Timeout | null>(null)

  // Load config from backend on mount
  React.useEffect(() => {
    loadConfig()
    loadWorkspaceInfo()
  }, [currentSessionId, sessions]) // Reload workspace info when session changes

  const loadConfig = async () => {
    try {
      const response = await fetch(`${API_URL}/api/config`)
      const data = await response.json()
      if (data.config) {
        setConfig(data.config)
      }
    } catch (error) {
      console.error('Error loading config:', error)
    }
  }

  const loadWorkspaceInfo = async () => {
    try {
      let url = `${API_URL}/api/workspace`
      if (currentSessionId) {
        const s = sessions.find(x => x.id === currentSessionId)
        if (s) {
          const rootPath = s.group ? `${s.group}/${s.workspace}` : s.workspace
          url += `?root=${encodeURIComponent(rootPath)}`
        }
      }

      const response = await fetch(url)
      const data = await response.json()
      // `workspace_root` is the server base root under which session workspaces are created.
      // `active_workspace_root` (optional) is the currently active run's workspace.
      if (data.workspace_root) {
        setWorkspaceRoot(data.workspace_root)
        loadHistoryForWorkspace(data.workspace_root)
      }
      // Optionally we could surface the active workspace to the UI if needed
      // if (data.active_workspace_root) setActiveWorkspace(data.active_workspace_root)
    } catch (e) {
      console.error('Failed to load workspace info', e)
    }
  }

  const historyStorageKey = (root: string) => `autods_history_${root}`

  const loadHistoryForWorkspace = (root: string) => {
    try {
      const raw = window.localStorage.getItem(historyStorageKey(root))
      const items = raw ? JSON.parse(raw) : []
      setHistoryList(items)
    } catch (e) {
      console.error('Failed to load history', e)
      setHistoryList([])
    }
  }

  // ==================== Session Management via Backend API ====================

  const loadSessions = async () => {
    try {
      const resp = await fetch(`${API_URL}/api/sessions`)
      const data = await resp.json()
      if (data.sessions) {
        setSessions(data.sessions)
      }
    } catch (e) {
      console.error('Failed to load sessions from backend', e)
      // Fallback: try to load from localStorage for migration
      try {
        const raw = window.localStorage.getItem(SESSIONS_KEY)
        const items = raw ? JSON.parse(raw) : []
        if (items.length > 0) {
          console.log('Migrating sessions from localStorage to backend...')
          // Migrate sessions to backend
          for (const session of items) {
            await fetch(`${API_URL}/api/sessions`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ name: session.name })
            })
          }
          // Clear localStorage after migration
          window.localStorage.removeItem(SESSIONS_KEY)
          // Reload from backend
          const resp = await fetch(`${API_URL}/api/sessions`)
          const data = await resp.json()
          if (data.sessions) {
            setSessions(data.sessions)
          }
        } else {
          setSessions([])
        }
      } catch (migrationError) {
        console.error('Failed to migrate sessions', migrationError)
        setSessions([])
      }
    }
  }

  const createSession = async (name?: string) => {
    try {
      const resp = await fetch(`${API_URL}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name || undefined })
      })
      const data = await resp.json()

      if (data.status === 'created' && data.session) {
        const newSession = data.session
        setSessions(prev => [newSession, ...prev])
        setCurrentSessionId(newSession.id)
        return newSession
      } else {
        console.error('Failed to create session:', data.message)
        throw new Error(data.message || 'Failed to create session')
      }
    } catch (e) {
      console.error('Failed to create session', e)
      throw e
    }
  }

  const deleteSession = async (id: number) => {
    try {
      const resp = await fetch(`${API_URL}/api/sessions/${id}`, {
        method: 'DELETE'
      })
      const data = await resp.json()

      if (data.status === 'success') {
        setSessions(prev => prev.filter(s => s.id !== id))
        if (currentSessionId === id) setCurrentSessionId(null)
      } else {
        console.error('Failed to delete session:', data.message)
      }
    } catch (e) {
      console.error('Failed to delete session', e)
    }
  }

  const saveSessionLogs = (id: number, logsToSave: any[]) => {
    // Update local state immediately for responsiveness
    setSessions(prev => prev.map(s => s.id === id ? { ...s, logs: logsToSave } : s))

    // Debounced save to backend (avoid too many API calls)
    // Clear any pending save
    if (saveLogsTimeoutRef.current) {
      clearTimeout(saveLogsTimeoutRef.current)
    }

    // Schedule a save after 2 seconds of inactivity
    saveLogsTimeoutRef.current = setTimeout(async () => {
      try {
        await fetch(`${API_URL}/api/sessions/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ logs: logsToSave })
        })
      } catch (e) {
        console.error('Failed to save session logs to backend', e)
      }
    }, 2000)
  }

  const saveHistoryForWorkspace = (root: string, items: Array<any>) => {
    try {
      window.localStorage.setItem(historyStorageKey(root), JSON.stringify(items))
    } catch (e) {
      console.error('Failed to save history', e)
    }
  }

  const addHistoryEntry = async () => {
    if (!workspaceRoot) return
    try {
      const resp = await fetch(`${API_URL}/api/files`)
      const data = await resp.json()
      const fileCount = Array.isArray(data.files) ? data.files.length : 0
      const entry = {
        id: Date.now(),
        createdAt: new Date().toISOString(),
        note: `Snapshot ${historyList.length + 1}`,
        fileCount
      }
      const newList = [entry, ...historyList]
      setHistoryList(newList)
      saveHistoryForWorkspace(workspaceRoot, newList)
    } catch (e) {
      console.error('Failed to add history entry', e)
    }
  }

  const deleteHistoryEntry = (id: number) => {
    if (!workspaceRoot) return
    const newList = historyList.filter((h) => h.id !== id)
    setHistoryList(newList)
    saveHistoryForWorkspace(workspaceRoot, newList)
  }

  const clearHistory = () => {
    if (!workspaceRoot) return
    setHistoryList([])
    saveHistoryForWorkspace(workspaceRoot, [])
  }

  // Poll status
  React.useEffect(() => {
    const pollStatus = async () => {
      try {
        const response = await fetch(`${API_URL}/api/status`)
        const data = await response.json()
        setStatus(data)

        // Track if agent has started
        if (data.is_running || data.logs.length > 0) {
          setHasStarted(true)
        }

        // If agent is running but we don't have a live session ID (e.g. after refresh),
        // try to find which session matches the active workspace.
        if (data.is_running && !liveSessionId && data.active_workspace && workspaceRoot && sessions.length > 0) {
          const activeWs = data.active_workspace.replace(/\\/g, '/')
          const baseRoot = workspaceRoot.replace(/\\/g, '/')
          
          const foundSession = sessions.find(s => {
            const groupPrefix = s.group ? `${s.group}/` : ''
            const sessionWs = `${baseRoot}/${groupPrefix}${s.workspace}`.replace(/\\/g, '/')
            return activeWs === sessionWs || activeWs.endsWith(sessionWs)
          })
          
          if (foundSession) {
            console.log('🚀 Reconnected to live session:', foundSession.name)
            setLiveSessionId(foundSession.id)
            setCurrentSessionId(foundSession.id)
            // Sync logs immediately to avoid flicker
            setSessions(prev => prev.map(s => s.id === foundSession.id ? { ...s, logs: data.logs || [] } : s))
          }
        }

        // If we are streaming logs into a session, save them
        if (liveSessionId) {
          try {
            saveSessionLogs(liveSessionId, data.logs || [])
          } catch (e) {
            console.error('Failed to save live logs into session', e)
          }
        }

        // Reset stop requested flag when agent is no longer running
        if (!data.is_running && stopRequested) {
          setStopRequested(false)
          if (stopTimeout) {
            clearTimeout(stopTimeout)
            setStopTimeout(null)
          }
        }

        // Clear live session tracking when run ends
        if (!data.is_running && liveSessionId) {
          // Immediate save when run ends (bypass debounce)
          if (saveLogsTimeoutRef.current) {
            clearTimeout(saveLogsTimeoutRef.current)
          }
          // Force immediate save to backend
          try {
            await fetch(`${API_URL}/api/sessions/${liveSessionId}`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ logs: data.logs || [] })
            })
          } catch (e) {
            console.error('Failed to save final logs to backend', e)
          }
          setLiveSessionId(null)
        }
      } catch (error) {
        console.error('Error polling status:', error)
      }
    }

    pollStatus()
    const interval = setInterval(pollStatus, 1000)
    return () => clearInterval(interval)
  }, [stopRequested, stopTimeout, liveSessionId, workspaceRoot])

  // load stored sessions on mount
  React.useEffect(() => {
    loadSessions()
  }, [])

  // If there are no sessions, automatically create a default one when we know the server base workspace
  React.useEffect(() => {
    const ensureDefaultSession = async () => {
      try {
        if (workspaceRoot && sessions.length === 0) {
          const s = await createSession('Default Session')
          setCurrentSessionId(s.id)
        } else if (sessions.length > 0 && currentSessionId === null) {
          // If sessions exist but none selected, pick the first
          setCurrentSessionId(sessions[0].id)
        }
      } catch (e) {
        console.error('Failed to ensure default session', e)
      }
    }
    ensureDefaultSession()
  }, [workspaceRoot, sessions.length])

  const handleSendMessage = async (message: string) => {
    // If waiting for input, send as input response
    if (status.waiting_for_input) {
      try {
        const response = await fetch(`${API_URL}/api/input`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: message })
        })
        const data = await response.json()
        if (data.status !== 'accepted') {
          alert(`Error: ${data.message}`)
        }
      } catch (error) {
        console.error('Error submitting input:', error)
        alert('Failed to submit input')
      }
    } else if (!status.is_running) {
      // Start new agent run with this goal
      try {
        // If a session is selected, start the run under its workspace
        let body: any = { goal: message, config }
        console.log('🔧 Sending config to backend:', config)
        if (currentSessionId) {
          const s = sessions.find(x => x.id === currentSessionId)
          if (s && s.workspace) {
            // If we know the server base workspace root, send the full path so the
            // backend will use the correct directory created by /api/create-workspace.
            // If the session has a group (e.g., 'workspacea'), include it.
            if (workspaceRoot) {
              const groupPrefix = s.group ? `${s.group}/` : ''
              body.workspace_root = `${workspaceRoot}/${groupPrefix}${s.workspace}`
            } else {
              // Fallback: send a relative path using group if present
              body.workspace_root = s.group ? `${s.group}/${s.workspace}` : s.workspace
            }
          }
        }

        const response = await fetch(`${API_URL}/api/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        })
        const data = await response.json()
        if (data.status === 'started') {
          console.log('Agent started successfully')
          setHasStarted(true)
          // Optionally clear previous logs for this session to start fresh
          if (currentSessionId) {
            saveSessionLogs(currentSessionId, [])
            // Mark this session as the live running session so we stream logs into it
            setLiveSessionId(currentSessionId)
          }
        } else {
          alert(`Error: ${data.message}`)
        }
      } catch (error) {
        console.error('Error starting agent:', error)
        alert('Failed to start agent')
      }
    }
  }

  const handleStop = async () => {
    try {
      setStopRequested(true)

      // Clear any existing timeout
      if (stopTimeout) clearTimeout(stopTimeout)

      const response = await fetch(`${API_URL}/api/stop`, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.status === 'requested') {
        console.log('Stop requested - Agent will stop at the next checkpoint')

        // Set a timeout to warn user if stop takes too long (120 seconds = 2 minutes)
        // This gives the agent time to:
        // 1. Finish current code execution (timeout is 60 seconds)
        // 2. Handle graceful shutdown
        const timeout = setTimeout(() => {
          if (stopRequested && status.is_running) {
            console.warn('Stop request still pending after 2 minutes')
            // Just log warning instead of forcing kill - let backend handle it
            alert('The agent is taking a long time to stop. This may indicate a long-running operation. Please wait or refresh the page.')
          }
        }, 120000) // 120 seconds / 2 minutes

        setStopTimeout(timeout as any)
      } else {
        alert(`Error: ${data.message}`)
        setStopRequested(false)
      }
    } catch (error) {
      console.error('Error stopping agent:', error)
      alert('Failed to stop agent')
      setStopRequested(false)
    }
  }

  const getStatusBadge = () => {
    if (stopRequested && status.is_running) {
      return (
        <span className="status-badge stopping">
          <i className="fas fa-power-off"></i> Stopping...
        </span>
      )
    }
    if (status.waiting_for_input) {
      return (
        <span className="status-badge waiting">
          <i className="fas fa-hourglass-half"></i> Waiting for Input
        </span>
      )
    }
    if (status.is_running) {
      return (
        <span className="status-badge running">
          <i className="fas fa-spinner fa-spin"></i> Running
        </span>
      )
    }
    return (
      <span className="status-badge idle">
        <i className="fas fa-circle"></i> Idle
      </span>
    )
  }

  // Extract input prompt from logs
  const inputPrompt = React.useMemo(() => {
    if (status.waiting_for_input && status.logs.length > 0) {
      const lastLog = status.logs[status.logs.length - 1]
      if (lastLog.type === 'input_request') {
        return lastLog.message
      }
    }
    return undefined
  }, [status.waiting_for_input, status.logs])

  // Get current workspace root for file operations
  const getCurrentWorkspaceRoot = () => {
    if (currentSessionId && workspaceRoot) {
      const s = sessions.find(x => x.id === currentSessionId)
      if (s) {
        const groupPrefix = s.group ? `${s.group}/` : ''
        return `${workspaceRoot}/${groupPrefix}${s.workspace}`
      }
    }
    return undefined
  }

  // File upload handler for ChatInterface
  const handleFileUpload = async (file: File) => {
    const wsRoot = getCurrentWorkspaceRoot()

    const formData = new FormData()
    formData.append('file', file)

    try {
      let url = `${API_URL}/api/upload-file`
      if (wsRoot) {
        url += `?root=${encodeURIComponent(wsRoot)}`
      }

      const response = await fetch(url, {
        method: 'POST',
        body: formData
      })
      const data = await response.json()
      if (data.status === 'success') {
        console.log(`File uploaded: ${data.filename}`)
        // Show a brief notification
        alert(`File uploaded: ${data.filename}`)
      } else {
        alert(`Upload failed: ${data.message}`)
      }
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('Failed to upload file')
    }
  }

  return (
    <div className={`agent-console ${showFiles ? 'files-open' : ''}`}>
      <div className="console-header">
        <h1>
          <i className="fas fa-robot"></i>
          AutoDS Agent Console
        </h1>
        <div className="header-actions">
          {getStatusBadge()}
          <button
            className={`btn-secondary ${showHistory ? 'active' : ''}`}
            onClick={() => setShowHistory(!showHistory)}
            title="Workspace History"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <i className="fas fa-history"></i> Sessions
          </button>
          {status.is_running && (
            <button
              className={`btn-danger ${stopRequested ? 'stopping' : ''}`}
              onClick={handleStop}
              disabled={stopRequested}
              title={stopRequested ? "Stop request sent, waiting for agent to stop..." : "Stop the running agent"}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <i className={`fas fa-${stopRequested ? 'hourglass-half' : 'stop'}`}></i>
              {stopRequested ? 'Stopping...' : 'Stop Agent'}
            </button>
          )}
          <button
            className={`btn-secondary ${showFiles ? 'active' : ''}`}
            onClick={() => setShowFiles(!showFiles)}
            title="Workspace Files"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <i className="fas fa-folder"></i> Files
          </button>
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            aria-label="Toggle theme"
          >
            <i className={`fas fa-${theme === 'dark' ? 'sun' : 'moon'}`}></i>
          </button>
        </div>
      </div>

      <div className="console-main" style={{ flexDirection: 'row' }}>
        {/* Left Sidebar: Sessions/History */}
        {showHistory && (
          <div className="history-panel sidebar-panel" style={{ width: '320px', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', background: 'var(--bg-panel)' }}>
            <div className="panel-header" style={{ padding: '18px 20px' }}>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                <i className="fas fa-layer-group" style={{ fontSize: '14px' }}></i> Sessions
              </h3>
              <button
                className="btn-text"
                onClick={() => setShowHistory(false)}
                style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.1)', border: 'none', color: 'white', cursor: 'pointer', width: '28px', height: '28px', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <i className="fas fa-times" style={{ fontSize: '12px' }}></i>
              </button>
            </div>
            <div style={{ padding: '16px', borderBottom: '1px solid var(--border-color)' }}>
              <button className="btn-primary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', padding: '12px 20px', fontSize: '14px' }} onClick={async () => {
                const name = window.prompt('Session name (optional):') || undefined
                await createSession(name)
              }} title="New Session">
                <i className="fas fa-plus"></i> New Session
              </button>
            </div>
            <div className="history-panel-body" style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
              {sessions.length === 0 ? (
                <div style={{ padding: '32px 16px', color: 'var(--text-muted)', textAlign: 'center' }}>
                  <i className="fas fa-inbox" style={{ fontSize: '32px', marginBottom: '12px', display: 'block', opacity: 0.5 }}></i>
                  <p style={{ margin: 0, fontSize: '14px' }}>No sessions yet</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {sessions.map((s, idx) => (
                    <div
                      key={s.id}
                      className={`session-item ${currentSessionId === s.id ? 'active' : ''}`}
                      onClick={() => setCurrentSessionId(s.id)}
                      style={{
                        padding: '14px 16px',
                        background: currentSessionId === s.id ? 'var(--accent-subtle)' : 'var(--bg-card)',
                        border: `1px solid ${currentSessionId === s.id ? 'var(--accent-color)' : 'var(--border-color)'}`,
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: '10px',
                          background: currentSessionId === s.id
                            ? 'var(--gradient-accent)'
                            : `linear-gradient(135deg, ${['#60a5fa', '#4ade80', '#f472b6', '#a78bfa', '#fbbf24'][idx % 5]} 0%, ${['#818cf8', '#22d3ee', '#fb923c', '#ec4899', '#f97316'][idx % 5]} 100%)`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          boxShadow: 'var(--shadow-sm)'
                        }}>
                          <i className="fas fa-comments" style={{ color: 'white', fontSize: '16px' }}></i>
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontWeight: 600,
                            color: currentSessionId === s.id ? 'var(--accent-color)' : 'var(--text-primary)',
                            fontSize: '14px',
                            marginBottom: '4px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}>{s.name}</div>
                          <div style={{
                            fontSize: '12px',
                            color: 'var(--text-muted)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px'
                          }}>
                            <i className="fas fa-clock" style={{ fontSize: '10px' }}></i>
                            {new Date(s.createdAt).toLocaleDateString()} {new Date(s.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '12px', marginLeft: '52px' }}>
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                          style={{
                            padding: '6px 10px',
                            fontSize: '11px',
                            fontWeight: 500,
                            background: 'var(--negative-bg)',
                            border: '1px solid transparent',
                            borderRadius: '6px',
                            color: 'var(--negative-color)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            transition: 'all 0.2s ease'
                          }}
                        >
                          <i className="fas fa-trash" style={{ fontSize: '10px' }}></i> Delete
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              const rootPath = s.group ? `${s.group}/${s.workspace}` : s.workspace
                              const resp = await fetch(`${API_URL}/api/files?root=${encodeURIComponent(rootPath)}`)
                              const data = await resp.json()
                              if (data.files) {
                                alert(`Files in ${rootPath}:\n${data.files.slice(0, 20).join('\n')}${data.files.length > 20 ? '...' : ''}`)
                              }
                            } catch (e) { alert('Failed to list files') }
                          }}
                          style={{
                            padding: '6px 10px',
                            fontSize: '11px',
                            fontWeight: 500,
                            background: 'var(--bg-elevated)',
                            border: '1px solid var(--border-color)',
                            borderRadius: '6px',
                            color: 'var(--text-secondary)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            transition: 'all 0.2s ease'
                          }}
                        >
                          <i className="fas fa-folder-open" style={{ fontSize: '10px' }}></i> Files
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Center: Chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
          {/* Progress bar now uses session-specific logs */}
          {(hasStarted || (currentSessionId && sessions.find(s => s.id === currentSessionId)?.logs?.length > 0)) && (
            <ProgressBar
              logs={currentSessionId ? (sessions.find(s => s.id === currentSessionId)?.logs || []) : status.logs}
              config={config}
            />
          )}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <ChatInterface
              logs={currentSessionId ? (sessions.find(s => s.id === currentSessionId)?.logs || []) : status.logs}
              onSendMessage={handleSendMessage}
              config={config}
              onConfigChange={setConfig}
              waitingForInput={status.waiting_for_input}
              inputPrompt={inputPrompt}
              onFileUpload={handleFileUpload}
              isAgentRunning={status.is_running}
            />
          </div>
        </div>

        {/* Right Sidebar: Files */}
        {showFiles && (
          <div className="files-panel sidebar-panel" style={{ width: '360px', borderLeft: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', background: 'var(--bg-panel)' }}>
            <div className="panel-header" style={{ padding: '18px 20px' }}>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                <i className="fas fa-folder-open" style={{ fontSize: '14px' }}></i> Workspace Files
              </h3>
              <button
                className="btn-text"
                onClick={() => setShowFiles(false)}
                style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.1)', border: 'none', color: 'white', cursor: 'pointer', width: '28px', height: '28px', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <i className="fas fa-times" style={{ fontSize: '12px' }}></i>
              </button>
            </div>
            <div className="files-panel-body" style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
              <FileManager isRunning={status.is_running} currentWorkspaceRoot={
                (() => {
                  if (currentSessionId && workspaceRoot) {
                    const s = sessions.find(x => x.id === currentSessionId)
                    if (s) {
                      const groupPrefix = s.group ? `${s.group}/` : ''
                      return `${workspaceRoot}/${groupPrefix}${s.workspace}`
                    }
                  }
                  return undefined
                })()
              } />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default AgentConsole
