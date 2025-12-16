import React from 'react'
import { LogEntry, SystemConfig } from '../types'

interface ProgressStep {
  id: string
  label: string
  icon: string
  status: 'pending' | 'active' | 'completed' | 'error'
  substeps?: string[]
}

interface ProgressBarProps {
  logs: LogEntry[]
  config?: SystemConfig
}

const ProgressBar: React.FC<ProgressBarProps> = ({ logs, config }) => {
  const [steps, setSteps] = React.useState<ProgressStep[]>([
    { id: 'init', label: 'Initialize', icon: 'fa-rocket', status: 'pending' },
    { id: 'research', label: 'Deep Research', icon: 'fa-microscope', status: 'pending' },
    { id: 'planning', label: 'Planning', icon: 'fa-clipboard-list', status: 'pending' },
    { id: 'execution', label: 'Execution', icon: 'fa-cogs', status: 'pending' },
    { id: 'complete', label: 'Complete', icon: 'fa-check-circle', status: 'pending' },
  ])

  React.useEffect(() => {
    // Build an ordered state machine based on latest relevant events
    // We define a mutable structure first
    const next: ProgressStep[] = [
      { id: 'init', label: 'Initialize', icon: 'fa-rocket', status: 'pending' },
      ...(config?.enable_deep_research ? [{ id: 'research', label: 'Deep Research', icon: 'fa-microscope', status: 'pending' } as ProgressStep] : []),
      { id: 'planning', label: 'Planning', icon: 'fa-clipboard-list', status: 'pending' },
      { id: 'execution', label: 'Execution', icon: 'fa-cogs', status: 'pending' },
      { id: 'complete', label: 'Complete', icon: 'fa-check-circle', status: 'pending' },
    ]

    // Helper: find step by ID
    const findStep = (id: string) => next.find(s => s.id === id)

    // Helper: find last index of a message containing a keyword
    const lastIndexOfMsg = (kw: string) => {
      for (let i = logs.length - 1; i >= 0; i--) {
        if (logs[i].message.includes(kw)) return i
      }
      return -1
    }

    const idxInitStart = Math.max(lastIndexOfMsg('Starting Agent System'), lastIndexOfMsg('Goal:'))
    const idxResearchStart = lastIndexOfMsg('Starting Deep Research')
    const idxResearchDone = Math.max(lastIndexOfMsg('Deep Research Complete'), lastIndexOfMsg('Research findings saved'))
    const idxResearchFail = lastIndexOfMsg('Deep Research failed')
    const idxPlanStart = lastIndexOfMsg('Generating Plan')
    const idxPlanDone = lastIndexOfMsg('Plan Generated')
    const idxExecStart = lastIndexOfMsg('Executing Step')
    const idxMissionDone = lastIndexOfMsg('Mission Complete')
    const execError = logs.some(l => l.type === 'error' && l.message.includes('Executing Step'))

    // Initialize
    const initStep = findStep('init')
    if (initStep && idxInitStart >= 0) initStep.status = 'completed'

    // Research (only set active/completed if started and step exists)
    const researchStep = findStep('research')
    if (researchStep) {
      if (idxResearchStart >= 0 && idxResearchFail === -1) {
        researchStep.status = idxResearchDone >= idxResearchStart ? 'completed' : 'active'
      } else if (idxResearchFail >= 0) {
        researchStep.status = 'error'
      }
    }

    // Planning
    const planningStep = findStep('planning')
    if (planningStep && idxPlanStart >= 0) {
      planningStep.status = idxPlanDone >= idxPlanStart ? 'completed' : 'active'
    }

    // Execution
    const execStep = findStep('execution')
    if (execStep && idxExecStart >= 0) {
      execStep.status = execError ? 'error' : 'active'
    }

    // Complete only after mission done
    const completeStep = findStep('complete')
    if (idxMissionDone >= 0) {
      if (execStep && execStep.status === 'pending') execStep.status = 'completed'
      if (completeStep) completeStep.status = 'completed'
    }

    setSteps(next)
  }, [logs, config?.enable_deep_research])

  return (
    <div className="progress-bar-container">
      <div className="progress-steps">
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            <div className={`progress-step progress-step-${step.status}`}>
              <div className="progress-step-icon">
                {step.status === 'completed' ? (
                  <i className="fas fa-check"></i>
                ) : step.status === 'error' ? (
                  <i className="fas fa-times"></i>
                ) : (
                  <i className={`fas ${step.icon}`}></i>
                )}
              </div>
              <div className="progress-step-label">{step.label}</div>
              {step.status === 'active' && (
                <div className="progress-step-spinner">
                  <i className="fas fa-spinner fa-spin"></i>
                </div>
              )}
            </div>
            {index < steps.length - 1 && (
              <div className={`progress-connector progress-connector-${steps[index + 1].status !== 'pending' ? 'active' : 'inactive'
                }`}></div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

export default ProgressBar

