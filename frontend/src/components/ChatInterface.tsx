import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import remarkGfm from 'remark-gfm'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { LogEntry, SystemConfig } from '../types'

interface ChatMessage {
  id: string
  type: 'system' | 'user' | 'agent' | 'step' | 'substep'
  content: string
  timestamp: number
  status?: 'success' | 'error' | 'warning' | 'info'
  collapsed?: boolean
  children?: ChatMessage[]
  metadata?: {
    stepId?: string
    agent?: string
    action?: string
  }
}

interface ChatInterfaceProps {
  logs: LogEntry[]
  onSendMessage: (message: string) => void
  config: SystemConfig
  onConfigChange: (config: SystemConfig) => void
  waitingForInput: boolean
  inputPrompt?: string
  onFileUpload?: (file: File) => Promise<void>
  isAgentRunning?: boolean
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  logs,
  onSendMessage,
  config,
  onConfigChange,
  waitingForInput,
  inputPrompt,
  onFileUpload,
  isAgentRunning = false
}) => {
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = React.useState('')
  const [showSettings, setShowSettings] = React.useState(false)
  const [isInPlanReview, setIsInPlanReview] = React.useState(false)
  const messagesEndRef = React.useRef<HTMLDivElement>(null)
  const messagesContainerRef = React.useRef<HTMLDivElement>(null)
  const [isAtBottom, setIsAtBottom] = React.useState(true)
  const [isUploading, setIsUploading] = React.useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0] && onFileUpload) {
      const file = e.target.files[0]
      setIsUploading(true)
      try {
        await onFileUpload(file)
      } finally {
        setIsUploading(false)
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      }
    }
  }

  // Convert logs to structured chat messages
  React.useEffect(() => {
    const structuredMessages: ChatMessage[] = []
    let currentStep: ChatMessage | null = null
    let messageId = 0

    logs.forEach((log, _index) => {
      const msg = log.message

      // System initialization
      if (msg.includes('Starting Agent System') || msg.includes('Goal:')) {
        structuredMessages.push({
          id: `msg-${messageId++}`,
          type: 'system',
          content: msg,
          timestamp: log.timestamp,
          status: 'info'
        })
      }
      // Deep Research Phase
      else if (msg.includes('Starting Deep Research')) {
        currentStep = {
          id: `msg-${messageId++}`,
          type: 'step',
          content: '🔬 Deep Research Phase',
          timestamp: log.timestamp,
          status: 'info',
          collapsed: false,
          children: [],
          metadata: { action: 'research' }
        }
        structuredMessages.push(currentStep)
      }
      else if (msg.includes('Executing Deep Research') || msg.includes('Research findings saved')) {
        if (currentStep && currentStep.metadata?.action === 'research') {
          currentStep.children?.push({
            id: `msg-${messageId++}`,
            type: 'substep',
            content: msg,
            timestamp: log.timestamp
          })
        }
      }
      else if (msg.includes('Deep Research Complete')) {
        if (currentStep && currentStep.metadata?.action === 'research') {
          currentStep.status = 'success'
          currentStep.collapsed = true
        }
        currentStep = null
      }
      // Final Report
      else if (msg.includes('Final Report')) {
        structuredMessages.push({
          id: `msg-${messageId++}`,
          type: 'agent',
          content: msg,
          timestamp: log.timestamp,
          status: 'success'
        })
      }
      // Planning Phase
      else if (msg.includes('Generating Plan') && !msg.includes('PLAN REVIEW')) {
        currentStep = {
          id: `msg-${messageId++}`,
          type: 'step',
          content: '📋 Generating Execution Plan',
          timestamp: log.timestamp,
          status: 'info',
          collapsed: false,
          children: [],
          metadata: { action: 'planning' }
        }
        structuredMessages.push(currentStep)
      }
      // PLAN REVIEW - add as child of planning step for expand/collapse
      // This message also contains "Plan Generated", so check this BEFORE the Plan Generated branch
      else if (msg.includes('PLAN REVIEW')) {
        // Find the planning step and add this as a child
        const planningStep = structuredMessages.find(m => m.metadata?.action === 'planning')
        if (planningStep && planningStep.children) {
          planningStep.children.push({
            id: `msg-${messageId++}`,
            type: 'substep',
            content: msg,
            timestamp: log.timestamp
          })
          // Also update the planning step status since PLAN REVIEW message contains "Plan Generated"
          planningStep.status = 'success'
          // Only auto-collapse if NOT in HITL mode (keep open for user review if HITL enabled)
          planningStep.collapsed = !config.enable_hitl
        } else {
          // Fallback: display as standalone
          structuredMessages.push({
            id: `msg-${messageId++}`,
            type: 'agent',
            content: msg,
            timestamp: log.timestamp,
            status: 'info'
          })
        }
        currentStep = null
      }
      else if (msg.includes('Plan Generated')) {
        // This branch handles cases where Plan Generated comes separately (without PLAN REVIEW)
        if (currentStep && currentStep.metadata?.action === 'planning') {
          currentStep.status = 'success'
          // Only auto-collapse if NOT in HITL mode (keep open for user review if HITL enabled)
          currentStep.collapsed = !config.enable_hitl
        }
        currentStep = null
      }
      // Execution Steps
      else if (msg.includes('Executing Step')) {
        const stepMatch = msg.match(/Executing Step (\d+):(.+)/)
        if (stepMatch) {
          currentStep = {
            id: `msg-${messageId++}`,
            type: 'step',
            content: `▶️ Step ${stepMatch[1]}:${stepMatch[2]}`,
            timestamp: log.timestamp,
            status: 'info',
            collapsed: false,
            children: [],
            metadata: { stepId: stepMatch[1], action: 'execution' }
          }
          structuredMessages.push(currentStep)
        }
      }
      else if (msg.includes('Selected Agent:') || msg.includes('Agent Selection')) {
        if (currentStep && currentStep.metadata?.action === 'execution') {
          currentStep.children?.push({
            id: `msg-${messageId++}`,
            type: 'substep',
            content: msg,
            timestamp: log.timestamp
          })
        }
      }
      else if (msg.includes('Step completed successfully') || msg.includes('✅')) {
        if (currentStep && currentStep.metadata?.action === 'execution') {
          currentStep.status = 'success'
          currentStep.collapsed = true
        }
      }
      else if (log.type === 'error') {
        if (currentStep) {
          currentStep.status = 'error'
          currentStep.children?.push({
            id: `msg-${messageId++}`,
            type: 'substep',
            content: msg,
            timestamp: log.timestamp,
            status: 'error'
          })
        } else {
          structuredMessages.push({
            id: `msg-${messageId++}`,
            type: 'agent',
            content: msg,
            timestamp: log.timestamp,
            status: 'error'
          })
        }
      }
      // Input requests
      else if (log.type === 'input_request') {
        structuredMessages.push({
          id: `msg-${messageId++}`,
          type: 'agent',
          content: msg,
          timestamp: log.timestamp,
          status: 'warning'
        })
      }
      // Mission Complete
      else if (msg.includes('Mission Complete')) {
        structuredMessages.push({
          id: `msg-${messageId++}`,
          type: 'system',
          content: '🏁 Mission Complete!',
          timestamp: log.timestamp,
          status: 'success'
        })
      }
      // Final report saved notification
      else if (msg.includes('Final report saved to')) {
        structuredMessages.push({
          id: `msg-${messageId++}`,
          type: 'system',
          content: msg,
          timestamp: log.timestamp,
          status: 'success'
        })
      }
      // Generic agent messages
      else if (!currentStep || !currentStep.children) {
        structuredMessages.push({
          id: `msg-${messageId++}`,
          type: 'agent',
          content: msg,
          timestamp: log.timestamp,
          status: log.type === 'success' ? 'success' : log.type === 'warning' ? 'warning' : undefined
        })
      } else {
        // Add as substep to current step
        currentStep.children.push({
          id: `msg-${messageId++}`,
          type: 'substep',
          content: msg,
          timestamp: log.timestamp
        })
      }
    })

    // Preserve user-controlled collapsed state from previous messages
    setMessages(prev => {
      const prevMap = new Map(prev.map(m => [m.id, m.collapsed]))
      return structuredMessages.map(m => {
        // Prefer persisted per-step collapse state (persist by stepId when available)
        let persisted: boolean | null = null
        try {
          const stepId = m.metadata?.stepId
          if (stepId && typeof window !== 'undefined' && window.localStorage) {
            const key = `autods_collapsed_step_${stepId}`
            const v = window.localStorage.getItem(key)
            if (v !== null) persisted = v === '1'
          }
        } catch (e) {
          // ignore storage errors
        }

        const fromPrev = prevMap.get(m.id)
        const defaultCollapsed = typeof m.collapsed === 'boolean' ? m.collapsed : (fromPrev ?? false)
        return {
          ...m,
          collapsed: persisted !== null ? persisted : defaultCollapsed
        }
      })
    })
  }, [logs])

  // Auto-scroll only when user has not scrolled up (isAtBottom true)
  React.useEffect(() => {
    if (isAtBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isAtBottom])

  // Track user scroll to disable auto-scrolling when user scrolls up
  // Attach listener on mount so it remains active across message updates and session switches
  React.useEffect(() => {
    const el = messagesContainerRef.current
    if (!el) return
    const onScroll = () => {
      const threshold = 80 // px from bottom to still consider as bottom
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
      setIsAtBottom(atBottom)
    }
    el.addEventListener('scroll', onScroll)
    // initialize
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  // Detect plan review phase
  React.useEffect(() => {
    if (waitingForInput && inputPrompt?.includes('Press Enter to approve the plan')) {
      setIsInPlanReview(true)
    } else {
      setIsInPlanReview(false)
    }
  }, [waitingForInput, inputPrompt])

  const handleSend = () => {
    if (inputValue.trim()) {
      onSendMessage(inputValue)
      setInputValue('')
    }
  }

  const toggleCollapse = (messageId: string) => {
    setMessages(prev => prev.map(msg => {
      if (msg.id !== messageId) return msg
      const newCollapsed = !msg.collapsed
      // Persist per-step collapse state when possible
      try {
        const stepId = msg.metadata?.stepId
        if (stepId && typeof window !== 'undefined' && window.localStorage) {
          const key = `autods_collapsed_step_${stepId}`
          window.localStorage.setItem(key, newCollapsed ? '1' : '0')
        }
      } catch (e) {
        // ignore storage errors
      }
      return { ...msg, collapsed: newCollapsed }
    }))
  }

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    return date.toLocaleTimeString()
  }

  // Parse and format plan content for better rendering
  const formatPlanContent = (content: string) => {
    // Extract plan steps from the PLAN REVIEW format
    // Format: "Step N: Task\n    └─ Description"
    const lines = content.split('\n')
    const steps: Array<{ stepNum: string; task: string; description: string }> = []

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      // Match "Step N: Task" pattern
      const stepMatch = line.match(/^Step\s+(\d+):\s*(.+)$/)
      if (stepMatch) {
        const stepNum = stepMatch[1]
        const task = stepMatch[2]
        // Check if next line is the description (starts with └─)
        let description = ''
        if (i + 1 < lines.length) {
          const nextLine = lines[i + 1].trim()
          if (nextLine.startsWith('└─')) {
            description = nextLine.replace('└─', '').trim()
            i++ // Skip the description line in next iteration
          }
        }
        steps.push({ stepNum, task, description })
      }
    }

    return steps
  }

  const renderMessage = (message: ChatMessage) => {
    const hasChildren = message.children && message.children.length > 0
    const isPlanReview = message.content.includes('PLAN REVIEW')

    return (
      <div key={message.id} className={`chat-message chat-message-${message.type} ${message.status ? `chat-message-${message.status}` : ''}`}>
        <div className="chat-message-header" onClick={() => hasChildren && toggleCollapse(message.id)}>
          <div className="chat-message-icon">
            {message.type === 'system' && <i className="fas fa-robot"></i>}
            {message.type === 'user' && <i className="fas fa-user"></i>}
            {message.type === 'agent' && <i className="fas fa-cog"></i>}
            {message.type === 'step' && (
              hasChildren ? (
                <i className={`fas ${message.collapsed ? 'fa-chevron-right' : 'fa-chevron-down'}`}></i>
              ) : (
                <i className="fas fa-circle-notch fa-spin"></i>
              )
            )}
          </div>
          <div className={`chat-message-content ${isPlanReview ? 'plan-review-content' : ''}`}>
            {isPlanReview ? (
              <div style={{
                background: 'var(--bg-panel)',
                border: '2px solid var(--accent-color)',
                borderRadius: '12px',
                padding: '20px',
                maxHeight: '450px',
                overflowY: 'auto'
              }}>
                {/* Header */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  marginBottom: '16px',
                  paddingBottom: '12px',
                  borderBottom: '1px solid var(--border-color)'
                }}>
                  <i className="fas fa-clipboard-list" style={{ color: 'var(--accent-color)', fontSize: '18px' }}></i>
                  <span style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-title)' }}>Execution Plan</span>
                </div>
                {/* Plan Steps */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {formatPlanContent(message.content).map((step, idx) => (
                    <div key={idx} style={{
                      display: 'flex',
                      gap: '12px',
                      padding: '12px',
                      background: 'var(--bg-main)',
                      borderRadius: '8px',
                      border: '1px solid var(--border-color)',
                      transition: 'all 0.2s'
                    }}>
                      <div style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%)',
                        color: 'white',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        fontSize: '14px',
                        flexShrink: 0
                      }}>
                        {step.stepNum}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                          {step.task}
                        </div>
                        {step.description && (
                          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                            {step.description}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {/* Fallback if parsing didn't find steps */}
                  {formatPlanContent(message.content).length === 0 && (
                    <pre style={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '13px',
                      lineHeight: '1.8',
                      color: 'var(--text-primary)'
                    }}>
                      {message.content}
                    </pre>
                  )}
                </div>
              </div>
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkMath, remarkGfm]}
                rehypePlugins={[rehypeKatex]}
              >
                {message.content}
              </ReactMarkdown>
            )}
          </div>
          {message.status && (
            <div className={`chat-message-status chat-status-${message.status}`}>
              {message.status === 'success' && <i className="fas fa-check-circle"></i>}
              {message.status === 'error' && <i className="fas fa-exclamation-circle"></i>}
              {message.status === 'warning' && <i className="fas fa-exclamation-triangle"></i>}
              {message.status === 'info' && <i className="fas fa-info-circle"></i>}
            </div>
          )}
        </div>
        {hasChildren && !message.collapsed && (
          <div className="chat-message-children">
            {message.children!.map(child => {
              const isChildPlanReview = child.content.includes('PLAN REVIEW')
              return (
                <div key={child.id} className={`chat-substep ${child.status ? `chat-substep-${child.status}` : ''}`}>
                  {isChildPlanReview ? (
                    <div style={{
                      background: 'var(--bg-panel)',
                      border: '2px solid var(--accent-color)',
                      borderRadius: '12px',
                      padding: '20px',
                      maxHeight: '450px',
                      overflowY: 'auto'
                    }}>
                      {/* Header */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        marginBottom: '16px',
                        paddingBottom: '12px',
                        borderBottom: '1px solid var(--border-color)'
                      }}>
                        <i className="fas fa-clipboard-list" style={{ color: 'var(--accent-color)', fontSize: '18px' }}></i>
                        <span style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-title)' }}>Execution Plan</span>
                      </div>
                      {/* Plan Steps */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {formatPlanContent(child.content).map((step, idx) => (
                          <div key={idx} style={{
                            display: 'flex',
                            gap: '12px',
                            padding: '12px',
                            background: 'var(--bg-main)',
                            borderRadius: '8px',
                            border: '1px solid var(--border-color)',
                            transition: 'all 0.2s'
                          }}>
                            <div style={{
                              width: '32px',
                              height: '32px',
                              borderRadius: '50%',
                              background: 'linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%)',
                              color: 'white',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 700,
                              fontSize: '14px',
                              flexShrink: 0
                            }}>
                              {step.stepNum}
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                                {step.task}
                              </div>
                              {step.description && (
                                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                  {step.description}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                        {/* Fallback if parsing didn't find steps */}
                        {formatPlanContent(child.content).length === 0 && (
                          <pre style={{
                            margin: 0,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            fontFamily: 'var(--font-mono)',
                            fontSize: '13px',
                            lineHeight: '1.8',
                            color: 'var(--text-primary)'
                          }}>
                            {child.content}
                          </pre>
                        )}
                      </div>
                    </div>
                  ) : child.content.includes('Final Report') ? (
                    <div className="chat-substep-content markdown-content">
                      <ReactMarkdown
                        remarkPlugins={[remarkMath, remarkGfm]}
                        rehypePlugins={[rehypeKatex]}
                      >
                        {child.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="chat-substep-content" style={{ whiteSpace: 'pre-wrap' }}>
                      {child.content}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
        <div className="chat-message-time">{formatTimestamp(message.timestamp)}</div>
      </div>
    )
  }

  return (
    <div className="chat-interface">
      {/* Settings Panel */}
      {showSettings && (
        <div className="chat-settings">
          <div className="chat-settings-header">
            <h3><i className="fas fa-sliders-h"></i> Agent Configuration</h3>
            <button onClick={() => setShowSettings(false)}>
              <i className="fas fa-times"></i>
            </button>
          </div>
          <div className="chat-settings-body">
            <label className="setting-item">
              <input
                type="checkbox"
                checked={config.enable_search_tool}
                onChange={(e) => onConfigChange({ ...config, enable_search_tool: e.target.checked })}
              />
              <span>Enable Web Search Tool</span>
            </label>
            <label className="setting-item">
              <input
                type="checkbox"
                checked={config.enable_hitl}
                onChange={(e) => onConfigChange({ ...config, enable_hitl: e.target.checked })}
              />
              <span>Enable Human-in-the-Loop (HITL)</span>
            </label>
            <label className="setting-item">
              <input
                type="checkbox"
                checked={config.enable_simple_task_check}
                onChange={(e) => onConfigChange({ ...config, enable_simple_task_check: e.target.checked })}
              />
              <span>Enable Simple Task Check</span>
            </label>
            <label className="setting-item">
              <input
                type="checkbox"
                checked={config.enable_deep_research}
                onChange={(e) => onConfigChange({ ...config, enable_deep_research: e.target.checked })}
              />
              <span>Enable Deep Research Phase</span>
            </label>
            {config.enable_deep_research && (
              <label className="setting-item setting-item-nested">
                <input
                  type="checkbox"
                  checked={config.deep_research_use_simple_goal}
                  onChange={(e) => onConfigChange({ ...config, deep_research_use_simple_goal: e.target.checked })}
                />
                <span>Use Simple Goal for Research</span>
              </label>
            )}
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="chat-messages" ref={messagesContainerRef}>
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <div style={{
              width: '88px',
              height: '88px',
              borderRadius: '24px',
              background: 'var(--gradient-accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '28px',
              boxShadow: 'var(--shadow-lg), var(--shadow-glow)',
              animation: 'float 4s ease-in-out infinite'
            }}>
              <i className="fas fa-robot" style={{ fontSize: '40px', color: 'white' }}></i>
            </div>
            <h2 style={{
              background: 'linear-gradient(135deg, var(--text-title) 0%, var(--accent-color) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>Welcome to AutoDS Agent</h2>
            <p>I'm your AI-powered data science assistant. Describe your task and I'll handle the research, planning, and execution for you.</p>
            <div className="chat-examples">
              <p style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
                <i className="fas fa-lightbulb" style={{ color: 'var(--warning-color)' }}></i>
                <strong>Try asking me to:</strong>
              </p>
              <div className="example-chips">
                <button onClick={() => setInputValue("Analyze customer data and create clustering visualizations")}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'linear-gradient(135deg, #60a5fa 0%, #818cf8 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <i className="fas fa-chart-pie" style={{ color: 'white', fontSize: '16px' }}></i>
                    </span>
                    <span>
                      <strong style={{ display: 'block', marginBottom: '2px' }}>Analyze & Cluster Data</strong>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Segment customers with ML</span>
                    </span>
                  </span>
                </button>
                <button onClick={() => setInputValue("Train a prediction model on sales dataset")}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'linear-gradient(135deg, #4ade80 0%, #22d3ee 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <i className="fas fa-brain" style={{ color: 'white', fontSize: '16px' }}></i>
                    </span>
                    <span>
                      <strong style={{ display: 'block', marginBottom: '2px' }}>Train ML Model</strong>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Build predictive models</span>
                    </span>
                  </span>
                </button>
                <button onClick={() => setInputValue("Generate comprehensive EDA report with visualizations")}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'linear-gradient(135deg, #f472b6 0%, #fb923c 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <i className="fas fa-chart-line" style={{ color: 'white', fontSize: '16px' }}></i>
                    </span>
                    <span>
                      <strong style={{ display: 'block', marginBottom: '2px' }}>Generate EDA Report</strong>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Comprehensive data insights</span>
                    </span>
                  </span>
                </button>
                <button onClick={() => setInputValue("Research latest trends in quantum computing")}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'linear-gradient(135deg, #a78bfa 0%, #ec4899 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <i className="fas fa-microscope" style={{ color: 'white', fontSize: '16px' }}></i>
                    </span>
                    <span>
                      <strong style={{ display: 'block', marginBottom: '2px' }}>Research Topics</strong>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Deep dive into any subject</span>
                    </span>
                  </span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map(renderMessage)}
            <div ref={messagesEndRef} />
            {!isAtBottom && (
              <div className="jump-to-latest" onClick={() => {
                messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
                setIsAtBottom(true)
              }}>Jump to latest</div>
            )}
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        {isInPlanReview ? (
          <>
            {/* Plan Review Mode */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              width: '100%',
              padding: '12px 0',
              borderTop: '1px solid var(--border-color)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                <div style={{ flex: 1, fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  <i className="fas fa-edit"></i> Plan Review
                </div>
                <button
                  className="btn-success"
                  onClick={() => {
                    onSendMessage('')
                    setInputValue('')
                  }}
                  style={{
                    padding: '10px 24px',
                    fontSize: '14px',
                    fontWeight: '600',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    boxShadow: '0 2px 8px rgba(39, 201, 63, 0.3)'
                  }}
                  title="Approve the generated plan and proceed with execution"
                >
                  <i className="fas fa-check-circle"></i> Approve Plan
                </button>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <textarea
                  className="chat-input"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && inputValue.trim()) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  placeholder="Or provide feedback to refine the plan... (Shift+Enter for new line)"
                  rows={2}
                  style={{ flex: 1 }}
                />
                <button
                  className="chat-send-button"
                  onClick={handleSend}
                  disabled={!inputValue.trim()}
                  style={{ padding: '0 20px', height: 'auto' }}
                  title="Send feedback to refine the plan"
                >
                  <i className="fas fa-paper-plane"></i> Refine
                </button>
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Normal Input Mode - Enhanced Design */}
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: 'none' }}
              onChange={handleFileSelect}
              disabled={isAgentRunning || isUploading}
            />

            {/* Input Container */}
            <div style={{
              flex: 1,
              display: 'flex',
              alignItems: 'flex-end',
              gap: '12px',
              padding: '12px 16px',
              background: 'transparent',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border-color)',
              transition: 'all 0.2s ease',
              position: 'relative'
            }}>
              {/* Left Actions */}
              <div style={{ display: 'flex', gap: '6px', flexShrink: 0, alignSelf: 'flex-end', paddingBottom: '2px' }}>
                <button
                  onClick={() => setShowSettings(!showSettings)}
                  title="Settings"
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: 'var(--radius-md)',
                    background: showSettings ? 'var(--accent-subtle)' : 'transparent',
                    border: showSettings ? '1px solid var(--accent-color)' : '1px solid transparent',
                    color: showSettings ? 'var(--accent-color)' : 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '15px',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <i className="fas fa-cog"></i>
                </button>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  title="Upload file to workspace"
                  disabled={isAgentRunning || isUploading}
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: 'var(--radius-md)',
                    background: 'transparent',
                    border: '1px solid transparent',
                    color: isAgentRunning ? 'var(--text-muted)' : 'var(--text-secondary)',
                    cursor: isAgentRunning ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '15px',
                    transition: 'all 0.2s ease',
                    opacity: isAgentRunning ? 0.5 : 1
                  }}
                >
                  {isUploading ? (
                    <i className="fas fa-spinner fa-spin"></i>
                  ) : (
                    <i className="fas fa-paperclip"></i>
                  )}
                </button>
              </div>

              {/* Text Input */}
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                placeholder={waitingForInput ? inputPrompt || "Agent is waiting for your input..." : "Describe your task or ask a question..."}
                rows={1}
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  resize: 'none',
                  color: 'var(--text-primary)',
                  fontSize: '15px',
                  lineHeight: '1.5',
                  fontFamily: 'var(--font-sans)',
                  padding: '8px 0',
                  minHeight: '24px',
                  maxHeight: '120px',
                  overflow: 'auto'
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = Math.min(target.scrollHeight, 120) + 'px'
                }}
              />

              {/* Send Button */}
              <button
                onClick={handleSend}
                disabled={!inputValue.trim()}
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: 'var(--radius-md)',
                  background: inputValue.trim() ? 'var(--gradient-accent)' : 'var(--bg-elevated)',
                  border: 'none',
                  color: inputValue.trim() ? 'white' : 'var(--text-muted)',
                  cursor: inputValue.trim() ? 'pointer' : 'not-allowed',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '16px',
                  transition: 'all 0.2s ease',
                  flexShrink: 0,
                  boxShadow: inputValue.trim() ? 'var(--shadow-sm)' : 'none'
                }}
              >
                <i className="fas fa-arrow-up"></i>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default ChatInterface
