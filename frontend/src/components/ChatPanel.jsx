import React, { useState, useRef, useEffect } from 'react'
import ToolCallLog from './ToolCallLog'
import SessionHistory from './SessionHistory'

const EXAMPLE_QUERIES = [
  'Investigate transaction TXN-015',
  'Trace fraud ring for ACC-004',
  'Find path between ACC-001 and ACC-006',
  'What accounts are linked to TXN-019?',
]

export default function ChatPanel({ messages, isLoading, onSend, history }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    const q = input.trim()
    if (!q || isLoading) return
    onSend(q)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      <div className="message-list">
        {messages.length === 0 && (
          <div style={{color: '#64748b', textAlign: 'center', marginTop: 40, fontSize: '0.9rem'}}>
            <div style={{fontSize: '2rem', marginBottom: 8}}>🔍</div>
            Start an investigation by typing a query or selecting an example below.
          </div>
        )}
        {messages.map(msg => (
          <div key={msg.id}>
            {msg.role === 'user' ? (
              <div className="user-message">{msg.content}</div>
            ) : (
              <div className="agent-message">
                <pre>{msg.content}</pre>
                {msg.steps && msg.steps.length > 0 && (
                  <ToolCallLog steps={msg.steps} />
                )}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            Investigating...
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <SessionHistory history={history} />
      <div className="query-chips">
        {EXAMPLE_QUERIES.map(q => (
          <button key={q} className="chip" onClick={() => onSend(q)}>
            {q}
          </button>
        ))}
      </div>
      <div className="query-input-area">
        <textarea
          className="query-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a transaction, account, or fraud pattern..."
          rows={1}
        />
        <button className="send-btn" onClick={handleSend} disabled={isLoading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
