import React from 'react'

interface InputModalProps {
  prompt: string
  onSubmit: (input: string) => void
  onCancel: () => void
}

const InputModal: React.FC<InputModalProps> = ({ prompt, onSubmit, onCancel }) => {
  const [input, setInput] = React.useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim()) {
      onSubmit(input)
      setInput('')
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3><i className="fas fa-keyboard"></i> User Input Required</h3>
        </div>
        <div className="modal-body">
          <p>{prompt}</p>
          <form onSubmit={handleSubmit}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Enter your response..."
              rows={4}
              autoFocus
              style={{
                width: '100%',
                boxSizing: 'border-box',
                resize: 'vertical',
                maxHeight: '300px',
                minHeight: '100px'
              }}
            />
          </form>
        </div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleSubmit}>
            Submit
          </button>
        </div>
      </div>
    </div>
  )
}

export default InputModal
