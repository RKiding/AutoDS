import React from 'react'
import API_URL from '../config/api'
import MarkdownViewer from './MarkdownViewer'

interface FileManagerProps {
  isRunning: boolean
  currentWorkspaceRoot?: string
}

interface WorkspaceInfo {
  workspace_root: string
  file_count: number
  total_size: number
}

const FileManager: React.FC<FileManagerProps> = ({ isRunning, currentWorkspaceRoot }) => {
  const [files, setFiles] = React.useState<string[]>([])
  const [workspaceInfo, setWorkspaceInfo] = React.useState<WorkspaceInfo | null>(null)
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null)
  const [expandInfo, setExpandInfo] = React.useState(false)
  const [expandUpload, setExpandUpload] = React.useState(false)
  const [expandedFolders, setExpandedFolders] = React.useState<Set<string>>(new Set())
  const [mdPreviewFile, setMdPreviewFile] = React.useState<string | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const loadFiles = async () => {
    try {
      const url = `${API_URL}/api/files` + (currentWorkspaceRoot ? `?root=${encodeURIComponent(currentWorkspaceRoot)}` : '')
      const response = await fetch(url)
      const data = await response.json()
      setFiles(data.files || [])
    } catch (error) {
      console.error('Error loading files:', error)
    }
  }

  const loadWorkspaceInfo = async () => {
    try {
      const url = `${API_URL}/api/workspace` + (currentWorkspaceRoot ? `?root=${encodeURIComponent(currentWorkspaceRoot)}` : '')
      const response = await fetch(url)
      const data = await response.json()
      setWorkspaceInfo(data)
    } catch (error) {
      console.error('Error loading workspace info:', error)
    }
  }

  React.useEffect(() => {
    loadFiles()
    loadWorkspaceInfo()
    const interval = setInterval(() => {
      loadFiles()
      loadWorkspaceInfo()
    }, 5000)
    return () => clearInterval(interval)
  }, [currentWorkspaceRoot])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0])
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const url = `${API_URL}/api/upload-file` + (currentWorkspaceRoot ? `?root=${encodeURIComponent(currentWorkspaceRoot)}` : '')
      const response = await fetch(url, {
        method: 'POST',
        body: formData
      })
      const data = await response.json()
      if (data.status === 'success') {
        alert(`File uploaded: ${data.filename}`)
        setSelectedFile(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
        loadFiles()
        loadWorkspaceInfo()
      } else {
        alert(`Error: ${data.message}`)
      }
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('Failed to upload file')
    }
  }

  const handleDownload = async (path: string) => {
    try {
      let url = `${API_URL}/api/download-file?path=${encodeURIComponent(path)}`
      if (currentWorkspaceRoot) {
        url += `&root=${encodeURIComponent(currentWorkspaceRoot)}`
      }
      window.open(url, '_blank')
    } catch (error) {
      console.error('Error downloading file:', error)
    }
  }

  const handlePreview = async (path: string) => {
    // Check if file is markdown
    if (path.endsWith('.md') || path.endsWith('.markdown')) {
      setMdPreviewFile(path)
    } else {
      // Default preview for other files
      try {
        let url = `${API_URL}/api/file-preview?path=${encodeURIComponent(path)}`
        if (currentWorkspaceRoot) {
          url += `&root=${encodeURIComponent(currentWorkspaceRoot)}`
        }
        const response = await fetch(url)
        const data = await response.json()
        if (data.content) {
          const newWindow = window.open('', '_blank')
          if (newWindow) {
            newWindow.document.write(`<pre>${data.content}</pre>`)
            newWindow.document.title = path
          }
        } else {
          alert(`Error: ${data.message}`)
        }
      } catch (error) {
        console.error('Error previewing file:', error)
      }
    }
  }

  const handleDelete = async (path: string) => {
    if (!confirm(`Are you sure you want to delete ${path}?`)) return

    try {
      let url = `${API_URL}/api/delete-file?path=${encodeURIComponent(path)}`
      if (currentWorkspaceRoot) {
        url += `&root=${encodeURIComponent(currentWorkspaceRoot)}`
      }
      const response = await fetch(url, {
        method: 'DELETE'
      })
      const data = await response.json()
      if (data.status === 'success') {
        alert(`File deleted: ${path}`)
        loadFiles()
        loadWorkspaceInfo()
      } else {
        alert(`Error: ${data.message}`)
      }
    } catch (error) {
      console.error('Error deleting file:', error)
      alert('Failed to delete file')
    }
  }

  const handleClearWorkspace = async () => {
    if (!confirm('Are you sure you want to clear the entire workspace? This cannot be undone!')) return

    try {
      const response = await fetch(`${API_URL}/api/clear-workspace`, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.status === 'success') {
        alert('Workspace cleared successfully')
        loadFiles()
        loadWorkspaceInfo()
      } else {
        alert(`Error: ${data.message}`)
      }
    } catch (error) {
      console.error('Error clearing workspace:', error)
      alert('Failed to clear workspace')
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  const toggleFolder = (folderPath: string) => {
    const newFolders = new Set(expandedFolders)
    if (newFolders.has(folderPath)) {
      newFolders.delete(folderPath)
    } else {
      newFolders.add(folderPath)
    }
    setExpandedFolders(newFolders)
  }

  // Group files by folder
  const organizeFilesByFolder = (fileList: string[]) => {
    const folderMap: { [key: string]: string[] } = {}
    const rootFiles: string[] = []

    fileList.forEach((file) => {
      const parts = file.split('/')
      if (parts.length > 1) {
        const folder = parts[0]
        if (!folderMap[folder]) folderMap[folder] = []
        folderMap[folder].push(file)
      } else {
        rootFiles.push(file)
      }
    })

    return { folderMap, rootFiles }
  }

  const { folderMap, rootFiles } = organizeFilesByFolder(files)

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', height: '100%', overflow: 'hidden' }}>
      {/* Workspace Info - Collapsed by default */}
      <div style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        overflow: 'hidden'
      }}>
        <div
          style={{
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            backgroundColor: 'var(--bg-hover)',
            transition: 'background 0.2s'
          }}
          onClick={() => setExpandInfo(!expandInfo)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <i className={`fas fa-chevron-${expandInfo ? 'down' : 'right'}`}></i>
            <span style={{ fontSize: '13px', fontWeight: 600 }}>Workspace Info</span>
          </div>
          {workspaceInfo && (
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              {workspaceInfo.file_count} files
            </span>
          )}
        </div>

        {expandInfo && workspaceInfo && (
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border-color)', fontSize: '13px' }}>
            <div style={{ marginBottom: '8px' }}>
              <div style={{ color: 'var(--text-secondary)', marginBottom: '2px' }}>Root:</div>
              <div style={{ color: 'var(--text-primary)', fontFamily: 'monospace', fontSize: '12px', wordBreak: 'break-all' }}>
                {workspaceInfo.workspace_root.split('/').pop()}
              </div>
            </div>
            <div style={{ marginBottom: '8px' }}>
              <div style={{ color: 'var(--text-secondary)', marginBottom: '2px' }}>Total Size:</div>
              <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                {formatSize(workspaceInfo.total_size)}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Upload Controls - Collapsed by default */}
      <div style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        overflow: 'hidden'
      }}>
        <div
          style={{
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            backgroundColor: 'var(--bg-hover)',
            transition: 'background 0.2s'
          }}
          onClick={() => setExpandUpload(!expandUpload)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <i className={`fas fa-chevron-${expandUpload ? 'down' : 'right'}`}></i>
            <span style={{ fontSize: '13px', fontWeight: 600 }}>Upload & Manage</span>
          </div>
        </div>

        {expandUpload && (
          <div style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileSelect}
              disabled={isRunning}
              style={{ fontSize: '12px' }}
            />
            {selectedFile && (
              <button
                className="btn-primary"
                onClick={handleUpload}
                disabled={isRunning}
                style={{ width: '100%', padding: '8px 12px', fontSize: '12px' }}
              >
                <i className="fas fa-upload"></i> Upload {selectedFile.name.substring(0, 20)}
              </button>
            )}
            <button
              className="btn-danger"
              onClick={handleClearWorkspace}
              disabled={isRunning}
              style={{ width: '100%', padding: '8px 12px', fontSize: '12px' }}
            >
              <i className="fas fa-trash-alt"></i> Clear Workspace
            </button>
          </div>
        )}
      </div>

      {/* File List */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontSize: '13px', fontWeight: 600, padding: '8px 0', color: 'var(--text-primary)' }}>
          <i className="fas fa-file"></i> Files
        </div>
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', minHeight: 0 }}>
          {files.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '20px',
              color: 'var(--text-secondary)',
              fontSize: '12px'
            }}>
              <i className="fas fa-folder" style={{ display: 'block', fontSize: '20px', marginBottom: '8px', opacity: 0.5 }}></i>
              No files
            </div>
          ) : (
            <>
              {/* Root level files */}
              {rootFiles.map((file, idx) => (
                <div key={`root-${idx}`} style={{
                  padding: '8px 12px',
                  background: 'var(--bg-panel)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  fontSize: '12px'
                }}>
                  <span style={{
                    flex: 1,
                    color: 'var(--text-primary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }} title={file}>
                    <i className="fas fa-file"></i> {file}
                  </span>
                  <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                    <button
                      onClick={() => handlePreview(file)}
                      style={{
                        background: 'var(--bg-hover)',
                        border: '1px solid var(--border-color)',
                        color: 'var(--text-primary)',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px'
                      }}
                    >
                      <i className="fas fa-eye"></i>
                    </button>
                    <button
                      onClick={() => handleDownload(file)}
                      style={{
                        background: 'var(--bg-hover)',
                        border: '1px solid var(--border-color)',
                        color: 'var(--text-primary)',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px'
                      }}
                    >
                      <i className="fas fa-download"></i>
                    </button>
                    <button
                      onClick={() => handleDelete(file)}
                      disabled={isRunning}
                      style={{
                        background: isRunning ? 'var(--bg-hover)' : 'var(--negative-color)',
                        border: '1px solid var(--border-color)',
                        color: isRunning ? 'var(--text-secondary)' : 'white',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: isRunning ? 'not-allowed' : 'pointer',
                        fontSize: '11px',
                        opacity: isRunning ? 0.5 : 1
                      }}
                    >
                      <i className="fas fa-trash"></i>
                    </button>
                  </div>
                </div>
              ))}

              {/* Folders with collapsible items */}
              {Object.entries(folderMap).map(([folder, folderFiles]) => (
                <div key={`folder-${folder}`}>
                  <div
                    onClick={() => toggleFolder(folder)}
                    style={{
                      padding: '8px 12px',
                      background: 'var(--bg-hover)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: 'var(--text-primary)',
                      transition: 'background 0.2s'
                    }}
                  >
                    <i className={`fas fa-chevron-${expandedFolders.has(folder) ? 'down' : 'right'}`}
                      style={{ fontSize: '11px', color: 'var(--accent-color)' }}>
                    </i>
                    <i className="fas fa-folder" style={{ fontSize: '12px', color: 'var(--accent-color)' }}></i>
                    <span>{folder}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                      {folderFiles.length} items
                    </span>
                  </div>

                  {expandedFolders.has(folder) && (
                    <div style={{ marginLeft: '12px', display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                      {folderFiles.map((file, idx) => (
                        <div key={`${folder}-${idx}`} style={{
                          padding: '6px 10px',
                          background: 'var(--bg-panel)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '6px',
                          fontSize: '11px'
                        }}>
                          <span style={{
                            flex: 1,
                            color: 'var(--text-primary)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }} title={file}>
                            <i className="fas fa-file"></i> {file.split('/').pop()}
                          </span>
                          <div style={{ display: 'flex', gap: '3px', flexShrink: 0 }}>
                            <button
                              onClick={() => handlePreview(file)}
                              style={{
                                background: 'var(--bg-hover)',
                                border: '1px solid var(--border-color)',
                                color: 'var(--text-primary)',
                                padding: '3px 6px',
                                borderRadius: '3px',
                                cursor: 'pointer',
                                fontSize: '10px'
                              }}
                            >
                              <i className="fas fa-eye"></i>
                            </button>
                            <button
                              onClick={() => handleDownload(file)}
                              style={{
                                background: 'var(--bg-hover)',
                                border: '1px solid var(--border-color)',
                                color: 'var(--text-primary)',
                                padding: '3px 6px',
                                borderRadius: '3px',
                                cursor: 'pointer',
                                fontSize: '10px'
                              }}
                            >
                              <i className="fas fa-download"></i>
                            </button>
                            <button
                              onClick={() => handleDelete(file)}
                              disabled={isRunning}
                              style={{
                                background: isRunning ? 'var(--bg-hover)' : 'var(--negative-color)',
                                border: '1px solid var(--border-color)',
                                color: isRunning ? 'var(--text-secondary)' : 'white',
                                padding: '3px 6px',
                                borderRadius: '3px',
                                cursor: isRunning ? 'not-allowed' : 'pointer',
                                fontSize: '10px',
                                opacity: isRunning ? 0.5 : 1
                              }}
                            >
                              <i className="fas fa-trash"></i>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Markdown Preview Modal */}
      {mdPreviewFile && (
        <MarkdownViewer
          filePath={mdPreviewFile}
          onClose={() => setMdPreviewFile(null)}
        />
      )}
    </div>
  )
}

export default FileManager