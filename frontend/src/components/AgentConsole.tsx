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
    logs: []
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

  const loadSessions = () => {
    try {
      const raw = window.localStorage.getItem(SESSIONS_KEY)
      const items = raw ? JSON.parse(raw) : []
      setSessions(items)
    } catch (e) {
      console.error('Failed to load sessions', e)
      setSessions([])
    }
  }

  const saveSessions = (items: Array<any>) => {
    try {
      window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(items))
      setSessions(items)
    } catch (e) {
      console.error('Failed to save sessions', e)
    }
  }

  const createSession = async (name?: string) => {
    const id = Date.now()
    const sessionName = name || `Session ${sessions.length + 1}`

    // Request backend to create a unique hashed workspace for this session
    // Group name under which all session workspaces will be created
    const SESSION_GROUP = 'workspacea'

    let workspace = `session_${id}`
    let group: string | undefined = undefined
    try {
      const resp = await fetch(`${API_URL}/api/create-workspace?group=${encodeURIComponent(SESSION_GROUP)}`, { method: 'POST' })
      const data = await resp.json()
      if (data && data.workspace) {
        workspace = data.workspace
        if (data.group) group = data.group
      } else {
        console.warn('create-workspace returned unexpected response, falling back to local workspace name')
      }
    } catch (e) {
      console.error('Failed to create workspace on server, using local fallback', e)
    }

    const s = { id, name: sessionName, workspace, group, logs: [], createdAt: new Date().toISOString() }
    const newList = [s, ...sessions]
    saveSessions(newList)
    setCurrentSessionId(id)
    return s
  }

  const deleteSession = async (id: number) => {
    const sessionToDelete = sessions.find(s => s.id === id)

    // Call backend to delete workspace
    if (sessionToDelete) {
      try {
        const params = new URLSearchParams()
        params.append('workspace', sessionToDelete.workspace)
        if (sessionToDelete.group) params.append('group', sessionToDelete.group)

        await fetch(`${API_URL}/api/delete-workspace?${params.toString()}`, {
          method: 'DELETE'
        })
      } catch (e) {
        console.error('Failed to delete workspace on server', e)
      }
    }

    const newList = sessions.filter(s => s.id !== id)
    saveSessions(newList)
    if (currentSessionId === id) setCurrentSessionId(null)
  }

  const saveSessionLogs = (id: number, logsToSave: any[]) => {
    setSessions(prev => {
      const newList = prev.map(s => s.id === id ? { ...s, logs: logsToSave } : s)
      try {
        window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(newList))
      } catch (e) { console.error(e) }
      return newList
    })
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
          <div className="history-panel sidebar-panel" style={{ width: '300px', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', background: 'var(--bg-panel)' }}>
            <div className="panel-header" style={{ padding: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                <i className="fas fa-history"></i> Sessions
              </h3>
              <button
                className="btn-text"
                onClick={() => setShowHistory(false)}
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div style={{ padding: '0 16px 16px', borderBottom: '1px solid var(--border-color)' }}>
              <button className="btn-primary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }} onClick={async () => {
                const name = window.prompt('Session name (optional):') || undefined
                await createSession(name)
              }} title="New Session">
                <i className="fas fa-plus"></i> New Session
              </button>
            </div>
            <div className="history-panel-body" style={{ flex: 1, overflowY: 'auto', padding: '0' }}>
              {sessions.length === 0 ? (
                <div style={{ padding: 16, color: 'var(--text-secondary)', textAlign: 'center' }}>No sessions yet.</div>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {sessions.map((s) => (
                    <li key={s.id} className={`session-item ${currentSessionId === s.id ? 'active' : ''}`} style={{
                      padding: '12px 16px',
                      borderBottom: '1px solid var(--border-color)',
                      background: currentSessionId === s.id ? 'var(--bg-hover)' : 'transparent',
                      cursor: 'pointer'
                    }}>
                      <div onClick={() => setCurrentSessionId(s.id)}>
                        <div style={{ fontWeight: 600, color: currentSessionId === s.id ? 'var(--accent-color)' : 'var(--text-primary)' }}>{s.name}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                          {new Date(s.createdAt).toLocaleDateString()} {new Date(s.createdAt).toLocaleTimeString()}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                        <button className="btn-xs" onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }} style={{ padding: '4px 8px', fontSize: '11px', background: 'var(--bg-main)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--negative-color)' }}>
                          <i className="fas fa-trash"></i>
                        </button>
                        <button className="btn-xs" onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            const rootPath = s.group ? `${s.group}/${s.workspace}` : s.workspace
                            const resp = await fetch(`${API_URL}/api/files?root=${encodeURIComponent(rootPath)}`)
                            const data = await resp.json()
                            if (data.files) {
                              alert(`Files in ${rootPath}:\n${data.files.slice(0, 20).join('\n')}${data.files.length > 20 ? '...' : ''}`)
                            }
                          } catch (e) { alert('Failed to list files') }
                        }} style={{ padding: '4px 8px', fontSize: '11px', background: 'var(--bg-main)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          <i className="fas fa-folder"></i>
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Center: Chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
          {hasStarted && <ProgressBar logs={status.logs} config={config} />}
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
          <div className="files-panel sidebar-panel" style={{ width: '320px', borderLeft: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', background: 'var(--bg-panel)' }}>
            <div className="panel-header" style={{ padding: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                <i className="fas fa-folder-open"></i> Workspace
              </h3>
              <button
                className="btn-text"
                onClick={() => setShowFiles(false)}
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="files-panel-body" style={{ flex: 1, overflowY: 'auto', padding: '0' }}>
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
