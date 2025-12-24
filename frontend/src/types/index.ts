export interface LogEntry {
  timestamp: number
  message: string
  type: 'log' | 'input_request' | 'control' | 'error' | 'success' | 'warning' | 'research' | 'execution'
}

export interface SystemStatus {
  is_running: boolean
  waiting_for_input: boolean
  logs: LogEntry[]
  active_workspace?: string | null
}

export interface WorkspaceInfo {
  workspace_root: string
  file_count: number
  total_size: number
}

export interface FileInfo {
  path: string
  name: string
}

export interface SystemConfig {
  enable_search_tool: boolean
  enable_hitl: boolean
  enable_simple_task_check: boolean
  enable_deep_research: boolean
  deep_research_use_simple_goal: boolean
}

export interface RunRequest {
  goal: string
  workspace_root?: string
  config?: Partial<SystemConfig>
}
