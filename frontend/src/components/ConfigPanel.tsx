import React from 'react'
import { SystemConfig } from '../types'

interface ConfigPanelProps {
  config: SystemConfig
  goal: string
  onConfigChange: (config: SystemConfig) => void
  onGoalChange: (goal: string) => void
  onRun: () => void
  onStop: () => void
  isRunning: boolean
}

const ConfigPanel: React.FC<ConfigPanelProps> = ({
  config,
  goal,
  onConfigChange,
  onGoalChange,
  onRun,
  onStop,
  isRunning
}) => {
  const goalExamples = [
    "Analyze the customer data and create a clustering visualization",
    "Train a prediction model on the sales dataset",
    "Generate a comprehensive EDA report with visualizations",
    "Research the latest trends in quantum computing and summarize findings"
  ]

  return (
    <div className="panel">
      <div className="panel-header">
        <h2><i className="fas fa-cog"></i> Configuration</h2>
      </div>
      <div className="panel-content">
        <div className="config-form">
          <div className="form-group">
            <label htmlFor="goal">
              <i className="fas fa-bullseye"></i> Task Goal
            </label>
            <textarea
              id="goal"
              value={goal}
              onChange={(e) => onGoalChange(e.target.value)}
              placeholder="Describe what you want the agent to accomplish..."
              rows={4}
              disabled={isRunning}
            />
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Examples:
              {goalExamples.map((example, idx) => (
                <div
                  key={idx}
                  style={{ 
                    cursor: isRunning ? 'not-allowed' : 'pointer',
                    padding: '4px 0',
                    opacity: isRunning ? 0.5 : 1
                  }}
                  onClick={() => !isRunning && onGoalChange(example)}
                >
                  • {example}
                </div>
              ))}
            </div>
          </div>

          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
            <label style={{ fontSize: '13px', fontWeight: 600, marginBottom: '12px', display: 'block' }}>
              <i className="fas fa-sliders-h"></i> Agent Settings
            </label>
            
            <div className="checkbox-group">
              <input
                type="checkbox"
                id="enable_search_tool"
                checked={config.enable_search_tool}
                onChange={(e) => onConfigChange({ ...config, enable_search_tool: e.target.checked })}
                disabled={isRunning}
              />
              <label htmlFor="enable_search_tool">
                Enable Web Search Tool
              </label>
            </div>

            <div className="checkbox-group">
              <input
                type="checkbox"
                id="enable_hitl"
                checked={config.enable_hitl}
                onChange={(e) => onConfigChange({ ...config, enable_hitl: e.target.checked })}
                disabled={isRunning}
              />
              <label htmlFor="enable_hitl">
                Enable Human-in-the-Loop (HITL)
              </label>
            </div>

            <div className="checkbox-group">
              <input
                type="checkbox"
                id="enable_simple_task_check"
                checked={config.enable_simple_task_check}
                onChange={(e) => onConfigChange({ ...config, enable_simple_task_check: e.target.checked })}
                disabled={isRunning}
              />
              <label htmlFor="enable_simple_task_check">
                Enable Simple Task Check
              </label>
            </div>

            <div className="checkbox-group">
              <input
                type="checkbox"
                id="enable_deep_research"
                checked={config.enable_deep_research}
                onChange={(e) => onConfigChange({ ...config, enable_deep_research: e.target.checked })}
                disabled={isRunning}
              />
              <label htmlFor="enable_deep_research">
                Enable Deep Research Phase
              </label>
            </div>

            {config.enable_deep_research && (
              <div className="checkbox-group" style={{ marginLeft: '26px' }}>
                <input
                  type="checkbox"
                  id="deep_research_use_simple_goal"
                  checked={config.deep_research_use_simple_goal}
                  onChange={(e) => onConfigChange({ ...config, deep_research_use_simple_goal: e.target.checked })}
                  disabled={isRunning}
                />
                <label htmlFor="deep_research_use_simple_goal">
                  Use Simple Goal for Research
                </label>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
            {!isRunning ? (
              <button
                className="btn-primary"
                onClick={onRun}
                disabled={!goal.trim()}
                style={{ flex: 1 }}
              >
                <i className="fas fa-play"></i> Start Agent
              </button>
            ) : (
              <button
                className="btn-danger"
                onClick={onStop}
                style={{ flex: 1 }}
              >
                <i className="fas fa-stop"></i> Stop Agent
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ConfigPanel
